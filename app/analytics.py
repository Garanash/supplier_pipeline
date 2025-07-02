import aiosqlite
from typing import Dict, List
from datetime import datetime, timedelta


async def get_analytics_data(user_id: int) -> Dict:
    """Получение данных для аналитики"""
    async with aiosqlite.connect("suppliers.db") as db:
        # Общая статистика
        cursor = await db.execute("""
            SELECT 
                COUNT(DISTINCT a.id) as total_articles,
                COUNT(DISTINCT s.id) as total_suppliers,
                COUNT(DISTINCT se.id) as total_emails
            FROM articles a
            LEFT JOIN suppliers s ON a.id = s.article_id
            LEFT JOIN sent_emails se ON s.id = se.supplier_id
            WHERE a.user_id = ?
        """, (user_id,))
        stats = await cursor.fetchone()

        # Статистика по странам
        cursor = await db.execute("""
            SELECT 
                s.country,
                COUNT(s.id) as supplier_count
            FROM suppliers s
            JOIN articles a ON s.article_id = a.id
            WHERE a.user_id = ?
            GROUP BY s.country
            ORDER BY supplier_count DESC
            LIMIT 10
        """, (user_id,))
        countries = await cursor.fetchall()

        # Статистика по регионам
        cursor = await db.execute("""
            SELECT 
                s.region,
                COUNT(s.id) as supplier_count
            FROM suppliers s
            JOIN articles a ON s.article_id = a.id
            WHERE a.user_id = ?
            GROUP BY s.region
            ORDER BY supplier_count DESC
        """, (user_id,))
        regions = await cursor.fetchall()

        # Статистика по статусам
        cursor = await db.execute("""
            SELECT 
                s.status,
                COUNT(s.id) as supplier_count
            FROM suppliers s
            JOIN articles a ON s.article_id = a.id
            WHERE a.user_id = ?
            GROUP BY s.status
            ORDER BY supplier_count DESC
        """, (user_id,))
        statuses = await cursor.fetchall()

        # Активность по дням
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        cursor = await db.execute("""
            SELECT 
                DATE(se.sent_at) as day,
                COUNT(se.id) as emails_sent
            FROM sent_emails se
            JOIN suppliers s ON se.supplier_id = s.id
            JOIN articles a ON s.article_id = a.id
            WHERE a.user_id = ? AND se.sent_at BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
        """, (user_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        activity = await cursor.fetchall()

        return {
            'total_articles': stats[0],
            'total_suppliers': stats[1],
            'total_emails': stats[2],
            'countries': [{'name': c[0], 'count': c[1]} for c in countries],
            'regions': [{'name': r[0], 'count': r[1]} for r in regions],
            'statuses': [{'name': s[0], 'count': s[1]} for s in statuses],
            'activity': [{'day': a[0], 'count': a[1]} for a in activity]
        }