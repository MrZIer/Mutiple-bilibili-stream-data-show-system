"""
在Django项目目录内运行的调试脚本
"""
import os
import sys
import django
import subprocess
import traceback
from pathlib import Path

# 设置Django环境
current_dir = Path(__file__).parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')

# 确保当前目录在Python路径中
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    django.setup()
    print("✅ Django环境初始化成功")
except Exception as e:
    print(f"❌ Django环境初始化失败: {e}")
    print("请确保您在Django项目根目录下运行此脚本")

def check_django_setup():
    """检查Django设置是否正确"""
    print("\n🔧 检查Django设置...")
    try:
        from django.conf import settings
        print(f"✅ Django项目根目录: {settings.BASE_DIR}")
        print(f"✅ 数据库配置: {settings.DATABASES['default']['ENGINE']}")
        
        # 检查应用是否正确注册
        if 'live_data' in settings.INSTALLED_APPS:
            print("✅ live_data应用已注册")
        else:
            print("❌ live_data应用未注册")
            
        return True
    except Exception as e:
        print(f"❌ Django设置检查失败: {e}")
        traceback.print_exc()
        return False

def check_database_connection():
    """检查数据库连接"""
    print("\n🗄️ 检查数据库连接...")
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        print("✅ 数据库连接正常")
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 数据库中的表: {len(tables)} 个")
        for table in tables:
            print(f"  - {table}")
        
        required_tables = ['live_rooms', 'danmaku_data', 'gift_data', 'monitoring_tasks', 'data_migration_logs']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ 缺少表: {missing_tables}")
            print("💡 请运行: python manage.py migrate")
            return False
        else:
            print(f"✅ 所有必需表都存在")
            return True
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        traceback.print_exc()
        return False

def check_redis_connection():
    """检查Redis连接"""
    print("\n📡 检查Redis连接...")
    try:
        from utils.redis_handler import get_redis_client
        redis_client = get_redis_client()
        
        # 测试连接
        redis_client.ping()
        print("✅ Redis连接正常")
        
        # 检查数据
        all_keys = redis_client.keys("*")
        print(f"📊 Redis总键数: {len(all_keys)}")
        
        if len(all_keys) == 0:
            print("⚠️ Redis中没有数据")
            print("💡 需要先运行数据收集器:")
            print("   cd ../web_version")
            print("   python multi_room_collector.py")
            return False
        
        # 检查特定类型的键
        patterns = {
            "房间弹幕": "room:*:danmaku",
            "房间礼物": "room:*:gifts", 
            "房间信息": "room:*:info",
            "监控任务": "task:*"
        }
        
        for pattern_name, pattern in patterns.items():
            keys = redis_client.keys(pattern)
            print(f"🔍 {pattern_name}: {len(keys)} 个键")
            
            # 显示前3个键的示例
            for i, key in enumerate(keys[:3]):
                if isinstance(key, bytes):
                    key_str = key.decode('utf-8')
                else:
                    key_str = str(key)
                print(f"  {i+1}. {key_str}")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入Redis处理器失败: {e}")
        print("💡 请检查 utils/redis_handler.py 文件是否存在")
        return False
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        print("💡 请确保:")
        print("  1. Redis服务器正在运行")
        print("  2. 数据收集器已经收集了数据")
        traceback.print_exc()
        return False

def check_file_structure():
    """检查文件结构"""
    print("\n📁 检查文件结构...")
    
    required_files = [
        "manage.py",
        "live_data/models.py",
        "live_data/management/__init__.py",
        "live_data/management/commands/__init__.py",
        "live_data/management/commands/sync_redis_to_db.py",
        "utils/__init__.py",
        "utils/redis_handler.py"
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in required_files:
        file_obj = Path(file_path)
        if file_obj.exists():
            print(f"✅ {file_path}")
            existing_files.append(file_path)
        else:
            print(f"❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️ 缺少文件: {missing_files}")
        return False
    else:
        print("\n✅ 所有必需文件都存在")
        return True

def check_management_commands():
    """检查管理命令是否存在"""
    print("\n⚙️ 检查管理命令...")
    try:
        from django.core.management import get_commands
        commands = get_commands()
        
        required_commands = ['sync_redis_to_db', 'start_sync_scheduler', 'check_redis_keys']
        existing_commands = []
        missing_commands = []
        
        for cmd in required_commands:
            if cmd in commands:
                existing_commands.append(cmd)
                print(f"✅ {cmd} 命令存在")
            else:
                missing_commands.append(cmd)
                print(f"❌ {cmd} 命令不存在")
        
        if missing_commands:
            print(f"\n💡 缺少的命令对应的文件:")
            for cmd in missing_commands:
                cmd_path = Path(f"live_data/management/commands/{cmd}.py")
                if cmd_path.exists():
                    print(f"  📁 文件存在但未识别: {cmd_path}")
                else:
                    print(f"  ❌ 文件不存在: {cmd_path}")
            return False
        else:
            print(f"✅ 所有管理命令都存在")
            return True
            
    except Exception as e:
        print(f"❌ 检查管理命令失败: {e}")
        traceback.print_exc()
        return False

def test_sync_command_directly():
    """直接测试同步命令"""
    print("\n🧪 测试同步命令...")
    
    try:
        # 测试导入
        from django.core.management import call_command
        print("✅ Django管理命令导入成功")
        
        # 测试是否能找到sync_redis_to_db命令
        try:
            from live_data.management.commands.sync_redis_to_db import Command
            print("✅ 同步命令类导入成功")
        except ImportError as e:
            print(f"❌ 同步命令类导入失败: {e}")
            return False
        
        # 测试试运行
        print("🔍 执行试运行...")
        try:
            call_command('sync_redis_to_db', '--dry-run', '--data-type', 'room', verbosity=1)
            print("✅ 试运行成功")
            return True
        except Exception as e:
            print(f"❌ 试运行失败: {e}")
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"❌ 测试同步命令失败: {e}")
        traceback.print_exc()
        return False

def run_detailed_sync_test():
    """运行详细的同步测试"""
    print("\n🔬 运行详细同步测试...")
    
    # 测试各个数据类型
    data_types = ['room', 'danmaku', 'gift', 'task']
    
    for data_type in data_types:
        print(f"\n🧪 测试 {data_type} 同步...")
        
        try:
            # 运行命令并捕获输出
            result = subprocess.run(
                [sys.executable, 'manage.py', 'sync_redis_to_db', '--data-type', data_type, '--dry-run', '-v', '1'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=Path.cwd()
            )
            
            print(f"📊 返回码: {result.returncode}")
            
            if result.stdout:
                print(f"📤 输出:")
                # 只显示前500个字符，避免输出过长
                output = result.stdout.strip()
                if len(output) > 500:
                    print(output[:500] + "...")
                else:
                    print(output)
            
            if result.stderr:
                print(f"❌ 错误:")
                error = result.stderr.strip()
                if len(error) > 500:
                    print(error[:500] + "...")
                else:
                    print(error)
            
            if result.returncode == 0:
                print(f"✅ {data_type} 同步测试成功")
            else:
                print(f"❌ {data_type} 同步测试失败")
                
        except Exception as e:
            print(f"❌ 运行 {data_type} 同步时异常: {e}")

def main():
    """主函数"""
    print("🔍 Django项目内 Redis同步诊断")
    print("=" * 50)
    print(f"📍 当前工作目录: {Path.cwd()}")
    
    # 检查是否在正确的Django项目目录中
    if not Path("manage.py").exists():
        print("❌ 当前目录没有manage.py文件")
        print("💡 请确保您在Django项目根目录下运行此脚本")
        print("   正确路径: g:\\Github_Project\\bilibili_data\\bilibili-live-monitor-django\\")
        return
    
    # 执行各项检查
    checks = [
        ("Django设置", check_django_setup),
        ("文件结构", check_file_structure),
        ("数据库连接", check_database_connection),
        ("Redis连接", check_redis_connection),
        ("管理命令", check_management_commands),
        ("同步命令", test_sync_command_directly)
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                failed_checks.append(check_name)
        except Exception as e:
            print(f"❌ {check_name} 检查异常: {e}")
            failed_checks.append(check_name)
    
    # 运行详细测试
    if not failed_checks:
        run_detailed_sync_test()
    
    # 总结报告
    print("\n" + "=" * 50)
    print("📊 诊断报告")
    print("=" * 50)
    
    if failed_checks:
        print(f"❌ 失败的检查项: {', '.join(failed_checks)}")
        print("\n💡 解决建议:")
        
        if "文件结构" in failed_checks:
            print("  🔧 创建缺失文件:")
            print("     mkdir live_data\\management")
            print("     mkdir live_data\\management\\commands") 
            print("     mkdir utils")
            print("     echo. > live_data\\management\\__init__.py")
            print("     echo. > live_data\\management\\commands\\__init__.py")
            print("     echo. > utils\\__init__.py")
        
        if "Redis连接" in failed_checks:
            print("  📡 Redis问题:")
            print("     cd ../web_version")
            print("     python multi_room_collector.py")
        
        if "数据库连接" in failed_checks:
            print("  🗄️ 数据库问题:")
            print("     python manage.py migrate")
        
    else:
        print("✅ 所有检查都通过了！")
        print("\n🎉 同步功能应该可以正常工作")
        print("\n📋 推荐的测试命令:")
        print("  python manage.py check_redis_keys --pattern 'room:*' --limit 5")
        print("  python manage.py sync_redis_to_db --dry-run")
        print("  python manage.py sync_redis_to_db")

if __name__ == '__main__':
    main()