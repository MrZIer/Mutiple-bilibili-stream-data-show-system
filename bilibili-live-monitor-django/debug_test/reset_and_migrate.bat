@echo off
echo 🔄 重置数据库和迁移...

echo 1. 停止Django进程...
taskkill /f /im python.exe 2>nul

echo 2. 删除数据库文件...
if exist db.sqlite3 del db.sqlite3

echo 3. 删除所有迁移文件...
if exist live_data\migrations\0*.py del live_data\migrations\0*.py

echo 4. 确保__init__.py存在...
if not exist live_data\migrations\__init__.py echo. > live_data\migrations\__init__.py

echo 5. 创建新迁移...
python manage.py makemigrations live_data

echo 6. 应用迁移...
python manage.py migrate

echo 7. 验证表结构...
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table';\")
tables = cursor.fetchall()
print('数据库表列表:')
for table in tables:
    print(f'  - {table[0]}')

# 验证DataMigrationLog表
from live_data.models import DataMigrationLog
print(f'\\nDataMigrationLog模型: {DataMigrationLog._meta.db_table}')
print('✅ 数据库重置完成！')
"

echo 8. 测试创建迁移日志...
python manage.py shell -c "
from live_data.models import DataMigrationLog
from django.utils import timezone

# 创建测试迁移日志
log = DataMigrationLog.objects.create(
    migration_type='all',
    start_time=timezone.now(),
    total_records=100,
    success_records=95,
    failed_records=5,
    status='completed'
)

print(f'✅ 测试迁移日志创建成功: {log}')
print(f'成功率: {log.get_success_rate():.1f}%')
"

pause