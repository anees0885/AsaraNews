"""
Database Seeder – Creates default categories, super admin, and sample data
"""

import json
from datetime import datetime, timedelta
from slugify import slugify

def seed_database():
    from app import app
    from models import db, User, Category, News, Event, Poll

    with app.app_context():
        # Check if already seeded
        if User.query.filter_by(role='super_admin').first():
            print('Database already seeded. Skipping.')
            return

        print('🌱 Seeding database...')

        # ─── Create Super Admin ──────────────────────────
        admin = User(
            username='superadmin',
            phone='9999999999',
            email='admin@gaavnews.com',
            role='super_admin',
            is_verified=True
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # Create a regular admin
        admin2 = User(
            username='admin',
            phone='9999999998',
            email='admin2@gaavnews.com',
            role='admin',
            is_verified=True
        )
        admin2.set_password('admin123')
        db.session.add(admin2)

        # Create a demo reporter
        reporter = User(
            username='reporter1',
            phone='8888888888',
            email='reporter@gaavnews.com',
            role='reporter',
            is_verified=True
        )
        reporter.set_password('reporter123')
        db.session.add(reporter)

        # Create a demo user
        user = User(
            username='villager1',
            phone='7777777777',
            email='user@gaavnews.com',
            role='registered',
            is_verified=True
        )
        user.set_password('user123')
        db.session.add(user)

        db.session.flush()

        # ─── Create Categories ──────────────────────────
        default_categories = [
            ('Breaking News', '🔴', 1),
            ('Panchayat', '🏛️', 2),
            ('Development', '🏗️', 3),
            ('Health', '🏥', 4),
            ('Education', '📚', 5),
            ('Events', '🎪', 6),
            ('Agriculture', '🌾', 7),
            ('Sports', '⚽', 8),
            ('Culture', '🎭', 9),
            ('Environment', '🌿', 10),
        ]

        categories = []
        for name, icon, priority in default_categories:
            cat = Category(
                name=name,
                slug=slugify(name),
                icon=icon,
                priority=priority,
                description=f'Latest {name.lower()} from the village',
                is_active=True
            )
            db.session.add(cat)
            categories.append(cat)

        db.session.flush()

        # ─── Create Sample News ─────────────────────────
        sample_news = [
            {
                'title': 'New Road Construction Begins in Asara Village',
                'description': 'The long-awaited road construction project has finally begun, connecting Asara village to the main highway.',
                'content': 'After years of petitions and requests from villagers, the state government has approved and begun construction of a 5-kilometer road connecting Asara village to the national highway. The project, worth Rs 2.5 crore, is expected to be completed within 6 months. Village Sarpanch Ramesh Patil expressed gratitude to the state government and said this would transform the village economy by improving access to markets and healthcare facilities. Workers have already started clearing the path and laying the foundation. The contractor has promised to employ local workers for the project.',
                'category': 2,  # Development
                'location': 'Asara Main Road',
                'status': 'approved'
            },
            {
                'title': 'Panchayat Approves Rs 10 Lakh Budget for School Renovation',
                'description': 'The village panchayat has unanimously approved a significant budget for renovating the primary school.',
                'content': 'In the monthly panchayat meeting held yesterday, members unanimously approved a budget of Rs 10 lakh for the renovation of Asara Primary School. The school, which was built 30 years ago, has been in desperate need of repairs. The renovation will include new roofing, construction of additional classrooms, installation of toilets, and a new playground. Education committee member Sunita Devi said the improved infrastructure will encourage more parents to send their children to school. The work is expected to begin next month.',
                'category': 1,  # Panchayat
                'location': 'Asara Panchayat Hall',
                'status': 'approved'
            },
            {
                'title': 'Free Health Camp Organized by District Hospital',
                'description': 'A free health check-up camp was organized providing medical services to over 200 villagers.',
                'content': 'The District Hospital organized a free health camp at Asara community hall last Sunday. Over 200 villagers benefited from free medical check-ups, including blood pressure monitoring, blood sugar tests, eye examinations, and dental check-ups. Dr. Priya Sharma, the chief medical officer, said that several cases of early-stage diabetes and hypertension were detected. Free medicines were distributed to patients who needed immediate treatment. The hospital has promised to organize such camps every quarter to ensure regular health monitoring for rural communities.',
                'category': 3,  # Health
                'location': 'Asara Community Hall',
                'status': 'approved'
            },
            {
                'title': 'Record Wheat Harvest Expected This Season',
                'description': 'Farmers in Asara village are expecting a bumper wheat crop this year due to favorable weather conditions.',
                'content': 'Favorable weather conditions and improved irrigation facilities have led farmers in Asara village to expect a record wheat harvest this season. Agriculture officer Mr. Suresh Kumar confirmed that the district is likely to see a 20% increase in wheat production compared to last year. Many farmers have adopted modern farming techniques and high-yield seed varieties recommended by the agriculture department. Farmer leader Bhagwan Das said the improved road connectivity has also helped in timely delivery of fertilizers and equipment. The harvest is expected to begin in the first week of April.',
                'category': 6,  # Agriculture
                'location': 'Asara Agricultural Zone',
                'status': 'approved'
            },
            {
                'title': 'Annual Village Festival Announced for Next Month',
                'description': 'The traditional annual village festival "Gaav Utsav" will be celebrated with great enthusiasm next month.',
                'content': 'The organising committee has announced that the annual "Gaav Utsav" festival will be held from March 15-17 at the village fairground. The three-day celebration will feature traditional folk music and dance performances, a local handicrafts exhibition, sports competitions for youth, a cattle fair, and food stalls serving traditional cuisine. Chief organizer Mahesh Yadav said that this year the festival will also include an agricultural technology exhibition to showcase modern farming tools. Cultural performances from neighboring villages have also been invited. Entry is free for all villagers.',
                'category': 5,  # Events
                'location': 'Asara Village Fairground',
                'status': 'approved'
            },
        ]

        for i, item in enumerate(sample_news):
            news = News(
                title=item['title'],
                slug=slugify(item['title']),
                description=item['description'],
                content=item['content'],
                category_id=categories[item['category']].id,
                author_id=reporter.id,
                location=item['location'],
                status=item['status'],
                event_date=datetime.utcnow() - timedelta(days=i * 2),
                view_count=(5 - i) * 50 + 30,
                like_count=(5 - i) * 10,
                comment_count=(5 - i) * 3,
                final_risk_score=10 + i * 5,
                moderation_decision='auto_published',
                created_at=datetime.utcnow() - timedelta(days=i * 2)
            )
            db.session.add(news)

        # ─── Create Sample Events ───────────────────────
        events = [
            Event(
                title='Gaav Utsav 2026',
                description='Annual village festival with cultural programs, sports, and exhibitions.',
                event_date=datetime.utcnow() + timedelta(days=20),
                event_time='09:00 AM',
                location='Asara Village Fairground',
                reminder_enabled=True,
                created_by=admin.id
            ),
            Event(
                title='Farmers Training Workshop',
                description='Workshop on modern farming techniques and subsidies.',
                event_date=datetime.utcnow() + timedelta(days=10),
                event_time='10:00 AM',
                location='Asara Community Hall',
                reminder_enabled=True,
                created_by=admin.id
            ),
        ]
        for e in events:
            db.session.add(e)

        # ─── Create Sample Polls ────────────────────────
        polls = [
            Poll(
                question='What should be the top priority for village development?',
                options=json.dumps(['Road Construction', 'Hospital Upgrade', 'School Improvement', 'Water Supply', 'Internet Connectivity']),
                created_by=admin.id,
                is_active=True,
                expires_at=datetime.utcnow() + timedelta(days=30)
            ),
            Poll(
                question='Which event would you like to see at Gaav Utsav?',
                options=json.dumps(['Cricket Tournament', 'Kabaddi Match', 'Music Concert', 'Dance Competition', 'Food Festival']),
                created_by=admin.id,
                is_active=True,
                expires_at=datetime.utcnow() + timedelta(days=15)
            ),
        ]
        for p in polls:
            db.session.add(p)

        db.session.commit()
        print('✅ Database seeded successfully!')
        print('─' * 40)
        print('📋 Default Accounts:')
        print('  Super Admin  → Phone: 9999999999 | Pass: admin123')
        print('  Admin        → Phone: 9999999998 | Pass: admin123')
        print('  Reporter     → Phone: 8888888888 | Pass: reporter123')
        print('  User         → Phone: 7777777777 | Pass: user123')
        print('─' * 40)


if __name__ == '__main__':
    seed_database()
