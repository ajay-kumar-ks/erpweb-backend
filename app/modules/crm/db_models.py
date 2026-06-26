from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, JSON, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.base import Base
from datetime import datetime

# Association table for many-to-many contact-tag relationship
contact_tags = Table(
    'contact_tags',
    Base.metadata,
    Column('contact_id', String, ForeignKey('contacts.id', ondelete='CASCADE')),
    Column('tag_id', String, ForeignKey('tags.id', ondelete='CASCADE'))
)


class Contact(Base):
    """
    Core Contact Record - Central entity for people/companies
    """
    __tablename__ = "contacts"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    company = Column(String, nullable=True, index=True)
    job_title = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)
    
    # Custom fields stored as JSON array: [{ label: "field_name", value: "field_value" }, ...]
    custom_fields = Column(JSON, default=list, nullable=False)
    
    # Status tracking
    status = Column(String, default='active')  # active, archived
    source = Column(String, nullable=True)  # how contact was acquired
    
    # Relationships
    tags = relationship(
        "Tag",
        secondary=contact_tags,
        back_populates="contacts",
        cascade="all, delete"
    )
    activities = relationship("Activity", back_populates="contact", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="contact")
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    archived_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    __table_args__ = (
        # common lookup patterns
        Index("ix_contacts_status", "status"),
        Index("ix_contacts_company_name", "company", "name"),
    )


class Tag(Base):
    """
    Tags for organizing and filtering contacts
    """
    __tablename__ = "tags"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    color = Column(String, default="#6366f1")
    
    contacts = relationship(
        "Contact",
        secondary=contact_tags,
        back_populates="tags"
    )
    
    created_at = Column(DateTime, default=func.now(), nullable=False)


class Activity(Base):
    """
    Activity timeline for contacts (calls, emails, meetings, notes)
    """
    __tablename__ = "activities"

    id = Column(String, primary_key=True, index=True)
    contact_id = Column(String, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    activity_type = Column(String, nullable=False)  # note, call, email, meeting, file
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # For follow-ups
    follow_up_date = Column(DateTime, nullable=True)
    
    # Flexible storage for type-specific data
    meta_data = Column(JSON, default=dict, nullable=False)
    
    contact = relationship("Contact", back_populates="activities")
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    leads = relationship("Lead", back_populates="pipeline")


class Phase(Base):
    __tablename__ = "phases"

    id = Column(String, primary_key=True, index=True)
    pipeline_id = Column(String, ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="#6b7280")
    position = Column(Integer, default=0)
    is_terminal = Column(Boolean, default=False)
    creates_client = Column(Boolean, default=False)  # Terminal phase that auto-converts leads to clients

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    leads = relationship("Lead", back_populates="phase")


class PipelineAssignment(Base):
    """
    Stores assignment configuration for each pipeline.
    Links departments to pipelines with assignment rules.
    """
    __tablename__ = "pipeline_assignments"

    id = Column(String, primary_key=True, index=True)
    pipeline_id = Column(String, ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False, unique=True)
    # JSON array: [{ department_id, department_name, assignment_mode, selected_members, individual_assignee_id, round_robin_index }]
    departments_config = Column(JSON, default=list, nullable=False)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    contact_id = Column(String, ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True)
    pipeline_id = Column(String, ForeignKey('pipelines.id', ondelete='SET NULL'), nullable=True)
    phase_id = Column(String, ForeignKey('phases.id', ondelete='SET NULL'), nullable=True)
    value = Column(Integer, nullable=True)
    expected_close_date = Column(DateTime, nullable=True)
    assignee = Column(String, nullable=True)
    source = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        # queries frequently filter by pipeline/phase/assignee and order by created_at
        Index("ix_leads_pipeline_id", "pipeline_id"),
        Index("ix_leads_phase_id", "phase_id"),
        Index("ix_leads_assignee", "assignee"),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_value", "value"),
    )

    # Relationships for convenient eager-loading
    contact = relationship("Contact", back_populates="leads", lazy="joined")
    pipeline = relationship("Pipeline", back_populates="leads", lazy="joined")
    phase = relationship("Phase", back_populates="leads", lazy="joined")


class Client(Base):
    """
    Client Record - A Contact/Lead that has been converted (deal won or relationship established)
    Phase 4.1: Inherits contact data + adds client-specific fields
    """
    __tablename__ = "clients"

    id = Column(String, primary_key=True, index=True)
    contact_id = Column(String, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False, unique=True)
    lead_id = Column(String, ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    
    # Client-specific fields
    client_since = Column(DateTime, default=func.now(), nullable=False)  # When converted to client
    account_manager = Column(String, nullable=True)  # Assigned HR user
    tier = Column(String, default='Standard')  # Standard, Premium, VIP
    status = Column(String, default='Active')  # Active, Inactive, Churned
    
    # 4.2: Additional tracking fields
    renewal_date = Column(DateTime, nullable=True)  # Next renewal/subscription date
    subscription_value = Column(Integer, nullable=True)  # Recurring revenue
    pinned_notes = Column(Text, nullable=True)  # Important internal notes
    internal_tags = Column(JSON, default=list, nullable=False)  # Internal-only tags for organization
    
    # Activity and linked deals
    activity_notes = Column(JSON, default=list, nullable=False)  # Activity history from lead
    linked_projects = Column(JSON, default=list, nullable=False)  # [{ project_id, project_name, module }]
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

