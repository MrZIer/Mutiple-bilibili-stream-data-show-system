#!/usr/bin/env python
import redis
import sys
import os
import subprocess
import time

def check_redis_service():
    """检查Redis服务状态"""
    print("🔍 检查Redis连接状态...")
    
    # 测试不同的连接配置
    redis_configs = [
        {'host': 'localhost', 'port': 6379, 'db': 0},
        {'host': '127.0.0.1', 'port': 6379, 'db': 0},
        {'host': 'localhost', 'port': 6380, 'db': 0},  # 备用端口
    ]
    
    for i, config in enumerate(redis_configs, 1):
        print(f"\n{i}️⃣ 测试配置: {config}")
        try:
            client = redis.Redis(**config, decode_responses=True, socket_timeout=5)
            result = client.ping()
            print(f"✅ Redis连接成功！Ping响应: {result}")
            
            # 测试基本操作
            client.set('test_key', 'test_value', ex=10)
            value = client.get('test_key')
            client.delete('test_key')
            
            print(f"✅ Redis读写操作正常，测试值: {value}")
            
            # 获取Redis信息
            info = client.info('server')
            print(f"📊 Redis版本: {info.get('redis_version', '未知')}")
            print(f"📊 运行时间: {info.get('uptime_in_seconds', 0)} 秒")
            
            # 检查现有数据
            keys = client.keys('*')
            print(f"📊 总键数量: {len(keys)}")
            
            # 检查Bilibili相关数据
            room_keys = client.keys('room:*')
            print(f"📊 房间数据键: {len(room_keys)}")
            
            if room_keys:
                print("✅ 找到Bilibili房间数据:")
                for key in room_keys[:5]:  # 显示前5个
                    if 'danmaku' in key:
                        count = client.llen(key)
                        print(f"   {key}: {count} 条记录")
                    elif 'info' in key:
                        info_data = client.hgetall(key)
                        uname = info_data.get('uname', '未知')
                        print(f"   {key}: {uname}")
            
            return config
            
        except redis.ConnectionError as e:
            print(f"❌ 连接失败: {e}")
        except redis.TimeoutError as e:
            print(f"❌ 连接超时: {e}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
    
    return None

def check_redis_installation():
    """检查Redis是否已安装"""
    print("\n🔍 检查Redis安装状态...")
    
    try:
        result = subprocess.run(['redis-server', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ Redis已安装: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Redis命令执行失败: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("❌ Redis命令响应超时")
    except FileNotFoundError:
        print("❌ Redis未安装或不在PATH中")
        print_installation_guide()
    except Exception as e:
        print(f"❌ 检查Redis安装失败: {e}")
    
    return False

def print_installation_guide():
    """打印Redis安装指南"""
    print("\n💡 Redis安装指南:")
    print("\n🪟 Windows:")
    print("1. 下载Redis for Windows:")
    print("   https://github.com/tporadowski/redis/releases")
    print("2. 或使用Chocolatey: choco install redis-64")
    print("3. 或使用WSL2:")
    print("   wsl --install")
    print("   sudo apt update && sudo apt install redis-server")
    
    print("\n🐳 Docker (推荐):")
    print("   docker pull redis:latest")
    print("   docker run -d -p 6379:6379 --name redis-server redis:latest")
    
    print("\n🐧 Linux:")
    print("   Ubuntu/Debian: sudo apt install redis-server")
    print("   CentOS/RHEL: sudo yum install redis")
    print("   Arch: sudo pacman -S redis")

def check_redis_process():
    """检查Redis进程是否在运行"""
    print("\n🔍 检查Redis进程...")
    
    try:
        if sys.platform == "win32":
            # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq redis-server.exe'], 
                                  capture_output=True, text=True, timeout=10)
            if 'redis-server.exe' in result.stdout:
                print("✅ Redis进程正在运行")
                return True
            else:
                print("❌ Redis进程未运行")
        else:
            # Linux/Mac
            result = subprocess.run(['pgrep', '-f', 'redis-server'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ Redis进程正在运行，PID: {result.stdout.strip()}")
                return True
            else:
                print("❌ Redis进程未运行")
    except Exception as e:
        print(f"❌ 检查进程失败: {e}")
    
    return False

def start_redis_service():
    """尝试启动Redis服务"""
    print("\n🚀 尝试启动Redis服务...")
    
    try:
        if sys.platform == "win32":
            # Windows
            commands = [
                ['net', 'start', 'Redis'],  # Windows服务
                ['redis-server', '--service-start'],  # 服务启动
                ['redis-server'],  # 直接启动
            ]
        else:
            # Linux/Mac
            commands = [
                ['sudo', 'systemctl', 'start', 'redis'],  # systemd
                ['sudo', 'service', 'redis-server', 'start'],  # service
                ['redis-server', '--daemonize', 'yes'],  # 后台启动
            ]
        
        for cmd in commands:
            try:
                print(f"📝 尝试命令: {' '.join(cmd)}")
                
                if cmd[-1] == 'redis-server':
                    # 对于直接启动redis-server，在后台运行
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE)
                    time.sleep(3)  # 等待启动
                    
                    if process.poll() is None:
                        print("✅ Redis服务器启动成功（后台运行）")
                        return True
                else:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"✅ 命令执行成功: {result.stdout}")
                        time.sleep(2)  # 等待服务启动
                        return True
                    else:
                        print(f"❌ 命令失败: {result.stderr}")
                        
            except subprocess.TimeoutExpired:
                print("❌ 命令超时")
            except FileNotFoundError:
                print("❌ 命令不存在")
            except Exception as e:
                print(f"❌ 执行失败: {e}")
    
    except Exception as e:
        print(f"❌ 启动Redis失败: {e}")
    
    return False

def start_redis_docker():
    """使用Docker启动Redis"""
    print("\n🐳 尝试使用Docker启动Redis...")
    
    try:
        # 检查Docker是否可用
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("❌ Docker不可用")
            return False
        
        print(f"✅ Docker可用: {result.stdout.strip()}")
        
        # 停止现有容器（如果存在）
        subprocess.run(['docker', 'stop', 'bilibili-redis'], 
                      capture_output=True, timeout=10)
        subprocess.run(['docker', 'rm', 'bilibili-redis'], 
                      capture_output=True, timeout=10)
        
        # 启动新的Redis容器
        cmd = [
            'docker', 'run', '-d',
            '--name', 'bilibili-redis',
            '-p', '6379:6379',
            'redis:latest'
        ]
        
        print(f"📝 启动命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ Docker Redis容器启动成功: {result.stdout.strip()}")
            time.sleep(3)  # 等待容器完全启动
            return True
        else:
            print(f"❌ Docker启动失败: {result.stderr}")
            
    except FileNotFoundError:
        print("❌ Docker未安装")
    except Exception as e:
        print(f"❌ Docker启动失败: {e}")
    
    return False

def test_django_redis():
    """测试Django中的Redis连接"""
    print("\n🔍 测试Django Redis连接...")
    
    try:
        # 设置Django环境
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
        
        import django
        django.setup()
        
        from utils.redis_config import test_redis_connection, get_redis_client
        
        print("📝 测试Django Redis配置...")
        if test_redis_connection():
            print("✅ Django Redis连接测试通过")
            
            # 测试获取客户端
            client = get_redis_client()
            info = client.info('server')
            print(f"✅ Django Redis客户端工作正常")
            print(f"   版本: {info.get('redis_version')}")
            print(f"   内存使用: {info.get('used_memory_human')}")
            
            return True
        else:
            print("❌ Django Redis连接测试失败")
            
    except Exception as e:
        print(f"❌ Django Redis测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def main():
    """主函数"""
    print("🔧 Redis连接诊断工具")
    print("=" * 50)
    
    # 1. 检查Redis安装
    print("\n📦 第一步：检查Redis安装")
    redis_installed = check_redis_installation()
    
    # 2. 检查Redis进程
    print("\n🔄 第二步：检查Redis进程")
    redis_running = check_redis_process()
    
    # 3. 测试Redis连接
    print("\n🔗 第三步：测试Redis连接")
    working_config = check_redis_service()
    
    if working_config:
        print(f"\n🎉 Redis连接正常！使用配置: {working_config}")
        
        # 4. 测试Django连接
        print("\n🔗 第四步：测试Django Redis连接")
        django_ok = test_django_redis()
        
        if django_ok:
            print("\n✅ 所有测试通过！Django应用可以正常连接Redis")
        else:
            print("\n⚠️ Django Redis连接有问题，请检查配置")
        
        return True
    
    # Redis连接失败，尝试启动
    print("\n❌ Redis连接失败，尝试启动Redis...")
    
    if not redis_running:
        # 尝试传统方式启动
        if start_redis_service():
            print("🔄 Redis启动后，重新检查连接...")
            time.sleep(2)
            working_config = check_redis_service()
            if working_config:
                print("🎉 现在Redis连接正常了！")
                return True
        
        # 尝试Docker启动
        if start_redis_docker():
            print("🔄 Docker Redis启动后，重新检查连接...")
            time.sleep(3)
            working_config = check_redis_service()
            if working_config:
                print("🎉 Docker Redis连接正常了！")
                return True
    
    # 所有尝试都失败
    print("\n❌ 无法启动Redis，请手动解决")
    print_installation_guide()
    
    print("\n💡 快速解决方案:")
    print("1. 使用Docker (推荐):")
    print("   docker run -d -p 6379:6379 --name redis-server redis:latest")
    print("\n2. 或者启动数据收集器中的Redis:")
    print("   cd g:\\Github_Project\\bilibili_data\\web_version\\")
    print("   python real_time_collector.py 24486091")
    
    return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)