"""
Enable creates_client on phases with name matching 'won' and create Client rows
for leads currently in those phases that lack a Client.
Run: python ensure_clients_for_terminal_phases.py
"""
from app.core.database import engine
from sqlalchemy.orm import sessionmaker
from app.modules.crm.db_models import Phase, Lead, Client
import uuid

Session = sessionmaker(bind=engine)

def main():
    session = Session()
    try:
        phases = session.query(Phase).filter(Phase.name.ilike('%won%')).all()
        if not phases:
            print('No "won" phases found.')
            return
        for p in phases:
            print('Phase:', p.id, p.name, 'creates_client=', getattr(p, 'creates_client', None))
            if not getattr(p, 'creates_client', False):
                print('  Enabling creates_client for this phase...')
                p.creates_client = True
                session.add(p)
                session.flush()
            leads = session.query(Lead).filter(Lead.phase_id == p.id).all()
            print('  Leads in phase:', len(leads))
            for l in leads:
                existing = session.query(Client).filter(Client.lead_id == l.id).first()
                if existing:
                    print('   Lead', l.id, 'already has client', existing.id)
                    continue
                if not l.contact_id:
                    print('   Lead', l.id, 'has no contact, skipping')
                    continue
                new_client = Client(
                    id=str(uuid.uuid4()),
                    contact_id=l.contact_id,
                    lead_id=l.id,
                    tier='Standard',
                    status='Active',
                    account_manager=l.assignee,
                )
                session.add(new_client)
                session.flush()
                print('   Created Client', new_client.id, 'for Lead', l.id)
        session.commit()
        print('Done')
    except Exception as e:
        session.rollback()
        print('Error:', e)
    finally:
        session.close()

if __name__ == '__main__':
    main()
