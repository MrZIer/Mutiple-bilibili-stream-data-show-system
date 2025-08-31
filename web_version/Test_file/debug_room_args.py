"""
诊断房间参数传递问题
"""
import subprocess
import sys
from pathlib import Path

def test_room_argument_passing():
    """测试房间参数传递"""
    print("🔍 测试房间参数传递...")
    
    # 测试命令
    test_rooms = "1962481108,22889484"
    collector_path = Path("web_version/multi_room_collector.py")
    
    if not collector_path.exists():
        print(f"❌ 收集器文件不存在: {collector_path}")
        return
    
    # 构建测试命令
    cmd = [
        sys.executable,
        str(collector_path),
        '--rooms', test_rooms,
        '--dry-run'  # 假设有这个参数用于测试
    ]
    
    print(f"🚀 执行命令: {' '.join(cmd)}")
    
    try:
        # 运行命令并捕获输出
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"📊 返回码: {result.returncode}")
        print(f"📤 标准输出:")
        print(result.stdout)
        
        if result.stderr:
            print(f"❌ 错误输出:")
            print(result.stderr)
            
    except subprocess.TimeoutExpired:
        print("⏰ 命令执行超时（这可能是正常的）")
    except Exception as e:
        print(f"❌ 执行失败: {e}")

def check_collector_code():
    """检查收集器代码中的参数解析"""
    print("\n🔍 检查收集器代码...")
    
    collector_path = Path("web_version/multi_room_collector.py")
    
    if not collector_path.exists():
        print(f"❌ 收集器文件不存在: {collector_path}")
        return
    
    try:
        with open(collector_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键代码片段
        checks = {
            "参数解析函数": "def parse_room_arguments",
            "argparse导入": "import argparse",
            "命令行解析": "ArgumentParser",
            "--rooms参数": "--rooms",
            "环境变量读取": "MONITOR_ROOMS",
            "硬编码房间列表": "room_ids = [",
        }
        
        found_issues = []
        
        for check_name, pattern in checks.items():
            if pattern in content:
                print(f"✅ {check_name}: 存在")
            else:
                print(f"❌ {check_name}: 不存在")
                found_issues.append(check_name)
        
        # 查找硬编码的房间列表
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'room_ids = [' in line and not line.strip().startswith('#'):
                print(f"\n⚠️ 发现硬编码房间列表在第 {i+1} 行:")
                # 显示前后几行
                start = max(0, i-2)
                end = min(len(lines), i+10)
                for j in range(start, end):
                    marker = ">>> " if j == i else "    "
                    print(f"{marker}{j+1:3d}: {lines[j]}")
                break
        
        return len(found_issues) == 0
        
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 房间参数传递问题诊断")
    print("="*50)
    
    # 检查代码
    code_ok = check_collector_code()
    
    # 测试参数传递
    test_room_argument_passing()
    
    print("\n" + "="*50)
    print("📊 诊断结果")
    print("="*50)
    
    if not code_ok:
        print("❌ 发现代码问题，可能的原因:")
        print("  1. 收集器没有正确实现参数解析")
        print("  2. 存在硬编码的房间列表覆盖了参数")
        print("  3. 参数解析逻辑有误")