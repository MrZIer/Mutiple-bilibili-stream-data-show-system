"""
测试所有表数据同步功能的完整脚本
"""
import os
import sys
import django
import json
from datetime import datetime

# 设置Django环境
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def test_redis_data_structure():
    """检查Redis中的数据结构"""
    print("🔍 步骤1：检查Redis数据结构")
    print("=" * 50)
    
    try:
        from utils.redis_handler import get_redis_client
        redis_client = get_redis_client()
        
        # 测试连接
        redis_client.ping()
        print("✅ Redis连接正常")
        
        # 检查各种类型的键
        key_patterns = {
            "房间弹幕": "room:*:danmaku",
            "房间礼物": "room:*:gifts", 
            "房间信息": "room:*:info",
            "监控任务": "task:*",
            "其他键": "*"
        }
        
        all_keys_count = 0
        for pattern_name, pattern in key_patterns.items():
            keys = redis_client.keys(pattern)
            print(f"📊 {pattern_name}: {len(keys)} 个键")
            
            # 显示前3个键的详细信息
            for i, key in enumerate(keys[:3]):
                if isinstance(key, bytes):
                    key_str = key.decode('utf-8')
                else:
                    key_str = str(key)
                
                key_type = redis_client.type(key)
                if isinstance(key_type, bytes):
                    key_type = key_type.decode('utf-8')
                
                print(f"  {i+1}. {key_str} (类型: {key_type})")
                
                # 根据类型显示数据量
                try:
                    if key_type == 'list':
                        length = redis_client.llen(key)
                        print(f"     数据量: {length} 条")
                    elif key_type == 'hash':
                        length = redis_client.hlen(key)
                        print(f"     字段数: {length} 个")
                    elif key_type == 'string':
                        value = redis_client.get(key)
                        if value:
                            print(f"     内容长度: {len(value)} 字节")
                except Exception as e:
                    print(f"     ❌ 读取失败: {e}")
            
            all_keys_count += len(keys)
            print()
        
        print(f"📈 Redis总键数: {all_keys_count}")
        return True
        
    except Exception as e:
        print(f"❌ Redis检查失败: {e}")
        return False

def test_database_before_sync():
    """检查同步前的数据库状态"""
    print("🗄️ 步骤2：检查同步前数据库状态")
    print("=" * 50)
    
    try:
        from live_data.models import LiveRoom, DanmakuData, GiftData, MonitoringTask, DataMigrationLog
        
        tables_info = {
            "直播间": LiveRoom.objects.count(),
            "弹幕数据": DanmakuData.objects.count(),
            "礼物数据": GiftData.objects.count(),
            "监控任务": MonitoringTask.objects.count(),
            "迁移日志": DataMigrationLog.objects.count()
        }
        
        print("📊 当前数据库记录数:")
        for table_name, count in tables_info.items():
            print(f"  {table_name}: {count} 条")
        
        return tables_info
        
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        return None

def test_sync_individual_tables():
    """逐个测试各表的同步功能"""
    print("\n🔄 步骤3：逐个测试表同步功能")
    print("=" * 50)
    
    sync_tests = [
        ('room', '🏠 房间信息'),
        ('danmaku', '💬 弹幕数据'),
        ('gift', '🎁 礼物数据'),
        ('task', '📋 监控任务')
    ]
    
    results = {}
    
    for data_type, description in sync_tests:
        print(f"\n{description} 同步测试:")
        print("-" * 30)
        
        try:
            # 先试运行
            print("  🔍 试运行...")
            os.system(f'cd bilibili-live-monitor-django && python manage.py sync_redis_to_db --data-type {data_type} --dry-run --quiet')
            
            # 实际同步
            print("  🚀 实际同步...")
            result = os.system(f'cd bilibili-live-monitor-django && python manage.py sync_redis_to_db --data-type {data_type}')
            
            if result == 0:
                print(f"  ✅ {description} 同步成功")
                results[data_type] = "成功"
            else:
                print(f"  ❌ {description} 同步失败")
                results[data_type] = "失败"
                
        except Exception as e:
            print(f"  ❌ {description} 同步异常: {e}")
            results[data_type] = f"异常: {e}"
    
    return results

def test_database_after_sync():
    """检查同步后的数据库状态"""
    print("\n📈 步骤4：检查同步后数据库状态")
    print("=" * 50)
    
    try:
        from live_data.models import LiveRoom, DanmakuData, GiftData, MonitoringTask, DataMigrationLog
        
        tables_info = {
            "直播间": LiveRoom.objects.count(),
            "弹幕数据": DanmakuData.objects.count(),
            "礼物数据": GiftData.objects.count(),
            "监控任务": MonitoringTask.objects.count(),
            "迁移日志": DataMigrationLog.objects.count()
        }
        
        print("📊 同步后数据库记录数:")
        for table_name, count in tables_info.items():
            print(f"  {table_name}: {count} 条")
        
        # 显示最新的迁移日志
        print("\n📋 最新迁移日志:")
        latest_logs = DataMigrationLog.objects.order_by('-created_at')[:3]
        for log in latest_logs:
            print(f"  时间: {log.start_time}")
            print(f"  类型: {log.get_migration_type_display()}")
            print(f"  状态: {log.get_status_display()}")
            print(f"  记录: 总数{log.total_records}, 成功{log.success_records}, 失败{log.failed_records}")
            if log.error_message:
                print(f"  详情: {log.error_message}")
            print("  ---")
        
        # 显示最新的数据样本
        print("\n📝 数据样本:")
        
        # 最新弹幕
        latest_danmaku = DanmakuData.objects.order_by('-timestamp')[:2]
        if latest_danmaku:
            print("  最新弹幕:")
            for dm in latest_danmaku:
                print(f"    {dm.username}: {dm.message} (房间{dm.room.room_id})")
        
        # 最新礼物
        latest_gifts = GiftData.objects.order_by('-timestamp')[:2]
        if latest_gifts:
            print("  最新礼物:")
            for gift in latest_gifts:
                print(f"    {gift.username} 送出 {gift.gift_name} x{gift.num} (房间{gift.room.room_id})")
        
        # 房间信息
        rooms = LiveRoom.objects.all()[:3]
        if rooms:
            print("  房间信息:")
            for room in rooms:
                print(f"    房间{room.room_id}: {room.title} - {room.uname}")
        
        return tables_info
        
    except Exception as e:
        print(f"❌ 同步后数据库检查失败: {e}")
        return None

def test_full_sync():
    """测试完整同步功能"""
    print("\n🎯 步骤5：测试完整同步功能")
    print("=" * 50)
    
    try:
        print("🚀 执行完整数据同步...")
        result = os.system('cd bilibili-live-monitor-django && python manage.py sync_redis_to_db --data-type all')
        
        if result == 0:
            print("✅ 完整同步成功")
            return True
        else:
            print("❌ 完整同步失败")
            return False
            
    except Exception as e:
        print(f"❌ 完整同步异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🎉 B站直播数据同步功能测试")
    print("=" * 60)
    
    # 步骤1：检查Redis数据
    if not test_redis_data_structure():
        print("❌ Redis数据检查失败，停止测试")
        return
    
    # 步骤2：检查同步前数据库状态
    before_sync = test_database_before_sync()
    if before_sync is None:
        print("❌ 数据库检查失败，停止测试")
        return
    
    # 步骤3：逐个测试表同步
    sync_results = test_sync_individual_tables()
    
    # 步骤4：检查同步后状态
    after_sync = test_database_after_sync()
    
    # 步骤5：测试完整同步
    full_sync_success = test_full_sync()
    
    # 最终检查
    final_check = test_database_after_sync()
    
    # 生成测试报告
    print("\n" + "=" * 60)
    print("📊 测试报告")
    print("=" * 60)
    
    print("🔍 同步前后数据对比:")
    if before_sync and after_sync and final_check:
        for table_name in before_sync.keys():
            before = before_sync[table_name]
            after = after_sync[table_name]
            final = final_check[table_name]
            increase = final - before
            print(f"  {table_name}: {before} -> {after} -> {final} (增加: {increase})")
    
    print("\n🎯 各表同步结果:")
    for data_type, result in sync_results.items():
        status = "✅" if result == "成功" else "❌"
        print(f"  {status} {data_type}: {result}")
    
    print(f"\n🚀 完整同步: {'✅ 成功' if full_sync_success else '❌ 失败'}")
    
    # 给出建议
    print("\n💡 建议:")
    if all(result == "成功" for result in sync_results.values()) and full_sync_success:
        print("  🎉 所有同步功能正常，可以启动定时同步服务！")
        print("  📋 运行命令: python setup.py")
    else:
        print("  ⚠️  部分同步功能存在问题，建议:")
        print("  1. 检查Redis服务是否正常运行")
        print("  2. 确保数据收集器已收集到数据")
        print("  3. 检查具体的错误日志")
        print("  4. 运行: python manage.py check_redis_keys")

if __name__ == '__main__':
    main()