import os
import subprocess
import sys

def run_command(command, description):
    """运行命令并处理错误"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def setup_django_project():
    """设置Django项目"""
    print("🚀 开始设置B站直播监控Django项目")
    
    # 1. 安装依赖
    if not run_command("pip install -r requirements.txt", "安装Python依赖"):
        return False
    
    # 2. 创建数据库迁移
    if not run_command("python manage.py makemigrations", "创建数据库迁移"):
        return False
    
    # 3. 执行迁移
    if not run_command("python manage.py migrate", "执行数据库迁移"):
        return False
    
    # 4. 创建超级用户（可选）
    print("\n📝 是否创建Django管理员账户？(y/n): ", end="")
    create_superuser = input().lower().strip()
    if create_superuser in ['y', 'yes']:
        run_command("python manage.py createsuperuser", "创建管理员账户")
    
    # 5. 收集静态文件
    run_command("python manage.py collectstatic --noinput", "收集静态文件")
    
    print("\n🎉 Django项目设置完成！")
    print("\n📋 下一步操作：")
    print("1. 确保Redis服务已启动")
    print("2. 运行: python manage.py runserver")
    print("3. 访问: http://127.0.0.1:8000")
    print("4. 管理后台: http://127.0.0.1:8000/admin")
    
    return True

if __name__ == "__main__":
    setup_django_project()