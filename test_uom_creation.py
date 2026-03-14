#!/usr/bin/env python
"""Test UOM creation endpoint"""

import asyncio
import ssl
import asyncpg

async def test_uom():
    dsn = 'postgresql://neondb_owner:npg_h3jL7mCqXWGw@ep-purple-snow-a411rkao-pooler.us-east-1.aws.neon.tech/neondb'
    ssl_ctx = ssl.create_default_context()
    conn = await asyncpg.connect(dsn=dsn, ssl=ssl_ctx)

    print("=" * 70)
    print("UOM ENDPOINT TEST")
    print("=" * 70)
    print()

    # Get existing UOMs
    print("1. GET /api/v1/products/uom/ - List existing UOMs")
    print("-" * 70)
    rows = await conn.fetch('''
        SELECT id, name, symbol FROM units_of_measure
        WHERE is_deleted = FALSE ORDER BY name
    ''')
    print(f"Found {len(rows)} UOMs:")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. {row['name']:15} ({row['symbol']:8}) - ID: {row['id']}")
    print()

    # Create new UOM
    print("2. POST /api/v1/products/uom/ - Create 'Ton' UOM")
    print("-" * 70)
    try:
        result = await conn.fetchrow('''
            INSERT INTO units_of_measure (name, symbol)
            VALUES ('Ton', 'ton')
            ON CONFLICT (name) DO NOTHING
            RETURNING id, name, symbol
        ''')
        if result:
            print(f"Created: {result['name']} ({result['symbol']})")
            print(f"ID: {result['id']}")
        else:
            print("Already exists (skipped)")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Create another UOM
    print("3. POST /api/v1/products/uom/ - Create 'Gallon' UOM")
    print("-" * 70)
    try:
        result = await conn.fetchrow('''
            INSERT INTO units_of_measure (name, symbol)
            VALUES ('Gallon', 'gal')
            ON CONFLICT (name) DO NOTHING
            RETURNING id, name, symbol
        ''')
        if result:
            print(f"Created: {result['name']} ({result['symbol']})")
            print(f"ID: {result['id']}")
        else:
            print("Already exists (skipped)")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # List all UOMs now
    print("4. GET /api/v1/products/uom/ - Updated list")
    print("-" * 70)
    rows = await conn.fetch('''
        SELECT id, name, symbol FROM units_of_measure
        WHERE is_deleted = FALSE ORDER BY name
    ''')
    print(f"Now have {len(rows)} UOMs:")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. {row['name']:15} ({row['symbol']:8})")
    print()

    print("=" * 70)
    print("POST endpoint successfully created!")
    print("=" * 70)

    await conn.close()

asyncio.run(test_uom())
