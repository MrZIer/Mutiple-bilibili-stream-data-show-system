# setup.py
import os
import sys
import subprocess
import threading
import time
import signal
from pathlib import Path

# 设置环境变量强制使用UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

def setup_environment():
    """初始化环境设置"""
    print("🔧 执行初始化任务...")
    
    # 确保必要的目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    print("✅ 初始化完成")

def start_collector():
    """启动爬虫程序"""
    try:
        print("🎯 启动数据收集器...")
        
        # 获取当前脚本的目录
        current_dir = Path(__file__).parent
        collector_path = current_dir / "web_version" / "multi_room_collector.py"
        
        if not collector_path.exists():
            print(f"❌ 收集器文件不存在: {collector_path}")
            return None
        
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONLEGACYWINDOWSSTDIO'] = '1'  # Windows兼容性
        
        # 启动收集器进程
        collector_process = subprocess.Popen(
            [sys.executable, str(collector_path)],
            cwd=current_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',  # 明确指定编码
            errors='replace',  # 遇到无法编码的字符时替换
            env=env
        )
        
        print("✅ 数据收集器已启动")
        return collector_process
        
    except Exception as e:
        print(f"❌ 启动数据收集器失败: {e}")
        return None

def start_sync_scheduler():
    """启动数据同步调度器"""
    try:
        print("⏰ 启动数据同步调度器...")
        
        # 获取当前脚本的目录
        current_dir = Path(__file__).parent
        manage_py = current_dir / "bilibili-live-monitor-django" / "manage.py"
        
        if not manage_py.exists():
            print(f"❌ manage.py文件不存在: {manage_py}")
            return None
        
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
        
        # 启动同步调度器
        sync_process = subprocess.Popen(
            [sys.executable, str(manage_py), "start_sync_scheduler", "--interval", "300"],
            cwd=manage_py.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        print("✅ 数据同步调度器已启动 (每5分钟同步一次)")
        return sync_process
        
    except Exception as e:
        print(f"❌ 启动数据同步调度器失败: {e}")
        return None

def start_django():
    """启动Django服务器"""
    try:
        print("🚀 启动Django服务器...")
        
        # 获取当前脚本的目录
        current_dir = Path(__file__).parent
        manage_py = current_dir / "bilibili-live-monitor-django" / "manage.py"
        
        if not manage_py.exists():
            print(f"❌ manage.py文件不存在: {manage_py}")
            return None
        
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
        
        # 启动Django服务器
        django_process = subprocess.Popen(
            [sys.executable, str(manage_py), "runserver", "0.0.0.0:8000"],
            cwd=manage_py.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        print("✅ Django服务器已启动")
        print("🌐 访问地址: http://localhost:8000/live/")
        return django_process
        
    except Exception as e:
        print(f"❌ 启动Django服务器失败: {e}")
        return None

def monitor_process(process, name):
    """监控进程输出"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                # 安全地处理可能包含特殊字符的输出
                try:
                    print(f"[{name}] {line.strip()}")
                except UnicodeEncodeError:
                    # 如果仍然有编码问题，移除或替换特殊字符
                    safe_line = line.strip().encode('utf-8', errors='replace').decode('utf-8')
                    print(f"[{name}] {safe_line}")
    except Exception as e:
        print(f"❌ 监控{name}进程失败: {e}")

def safe_print(text):
    """安全打印函数，处理编码问题"""
    try:
        print(text)
    except UnicodeEncodeError:
        # 移除emoji和特殊字符
        safe_text = text.encode('ascii', errors='ignore').decode('ascii')
        print(safe_text)

def main():
    """主函数"""
    # 尝试设置控制台编码为UTF-8
    try:
        if sys.platform == 'win32':
            import locale
            import codecs
            
            # 设置标准输出编码
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
            
            # 设置控制台代码页为UTF-8
            os.system('chcp 65001 >nul 2>&1')
    except:
        pass  # 如果设置失败，继续运行
    
    safe_print("="*60)
    safe_print("🎉 B站直播监控系统启动器")
    safe_print("="*60)
    
    # 初始化环境
    setup_environment()
    
    # 存储进程对象
    processes = {}
    monitor_threads = []
    
    try:
        # 启动数据收集器
        collector_process = start_collector()
        if collector_process:
            processes['collector'] = collector_process
            
            # 启动监控线程
            collector_thread = threading.Thread(
                target=monitor_process, 
                args=(collector_process, "收集器"),
                daemon=True
            )
            collector_thread.start()
            monitor_threads.append(collector_thread)
        
        # 等待一会让收集器完全启动
        time.sleep(3)
        
        # 启动数据同步调度器
        sync_process = start_sync_scheduler()
        if sync_process:
            processes['sync'] = sync_process
            
            # 启动监控线程
            sync_thread = threading.Thread(
                target=monitor_process, 
                args=(sync_process, "同步器"),
                daemon=True
            )
            sync_thread.start()
            monitor_threads.append(sync_thread)
        
        # 等待一会让同步器启动
        time.sleep(2)
        
        # 启动Django服务器
        django_process = start_django()
        if django_process:
            processes['django'] = django_process
            
            # 启动监控线程
            django_thread = threading.Thread(
                target=monitor_process, 
                args=(django_process, "Django"),
                daemon=True
            )
            django_thread.start()
            monitor_threads.append(django_thread)
        
        if not processes:
            safe_print("❌ 没有成功启动任何服务")
            return
        
        safe_print("\n" + "="*60)
        safe_print("✅ 所有服务已启动！")
        safe_print("🎯 数据收集器: 收集B站直播数据到Redis")
        safe_print("⏰ 数据同步器: 每5分钟将Redis数据同步到SQLite")
        safe_print("🌐 Web界面: http://localhost:8000/live/")
        safe_print("💡 按 Ctrl+C 停止所有服务")
        safe_print("="*60)
        
        # 等待中断信号
        try:
            while True:
                # 检查进程是否还在运行
                running_processes = []
                for name, process in processes.items():
                    if process.poll() is None:  # 进程还在运行
                        running_processes.append(name)
                    else:
                        safe_print(f"⚠️ {name}进程已停止")
                
                if not running_processes:
                    safe_print("❌ 所有进程都已停止")
                    break
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            safe_print("\n💡 收到停止信号...")
    
    except Exception as e:
        safe_print(f"❌ 启动过程中发生错误: {e}")
    
    finally:
        # 停止所有进程
        safe_print("🛑 正在停止所有服务...")
        
        for name, process in processes.items():
            try:
                safe_print(f"⏳ 停止{name}...")
                process.terminate()
                
                # 等待进程结束，超时后强制杀死
                try:
                    process.wait(timeout=10)
                    safe_print(f"✅ {name}已停止")
                except subprocess.TimeoutExpired:
                    safe_print(f"⚠️ {name}超时，强制终止...")
                    process.kill()
                    process.wait()
                    
            except Exception as e:
                safe_print(f"❌ 停止{name}失败: {e}")
        
        safe_print("🏁 所有服务已停止")

if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, lambda s, f: None)
    signal.signal(signal.SIGTERM, lambda s, f: None)
    
    main()