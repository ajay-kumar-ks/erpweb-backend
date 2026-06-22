"""
Quick diagnostic script: list leads currently in phases named 'Won' and check for Client rows linked by lead_id.
Run from repository root: python backend/check_clients.py
"""
from app.core.database import engine
from sqlalchemy.orm import sessionmaker
from app.modules.crm.db_models import Phase, Lead, Client
from sqlalchemy import select

Session = sessionmaker(bind=engine)

def main():
    session = Session()
    try:
        # find phases named Won (case-insensitive)
        won_phases = session.query(Phase).filter(Phase.name.ilike('%won%')).all()
        if not won_phases:
            print('No phases with name containing "won" found.')
            return
        print(f'Found {len(won_phases)} phase(s) matching "won":')
        for p in won_phases:
            print('\nPhase:', p.id, p.name, 'creates_client=', getattr(p, 'creates_client', None))
            leads = session.query(Lead).filter(Lead.phase_id == p.id).all()
            print(f'  Leads in this phase: {len(leads)}')
            for l in leads:
                print('   Lead:', l.id, l.title, 'contact_id=', l.contact_id)
                client = session.query(Client).filter(Client.lead_id == l.id).first()
                if client:
                    print('     -> Client exists:', client.id, 'contact_id=', client.contact_id)
                else:
                    print('     -> No Client found for this lead')
    finally:
        session.close()

if __name__ == '__main__':
    main()
