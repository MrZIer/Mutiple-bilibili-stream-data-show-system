#!/usr/bin/env python
import os
import sys
import django
import requests
import json

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def test_api_endpoints():
    """测试API端点是否正常"""
    print("🔍 测试API端点...")
    
    base_url = "http://localhost:8000"
    api_endpoints = [
        '/live/api/redis/status/',
        '/live/api/system/stats/',
        '/live/api/rooms/',
    ]
    
    api_results = {}
    
    for endpoint in api_endpoints:
        try:
            print(f"\n📡 测试 {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   响应数据: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...")
                    api_results[endpoint] = {'status': 'success', 'data': data}
                except:
                    print(f"   响应内容: {response.text[:200]}...")
                    api_results[endpoint] = {'status': 'invalid_json', 'content': response.text}
            else:
                print(f"   错误响应: {response.text}")
                api_results[endpoint] = {'status': 'error', 'code': response.status_code}
                
        except requests.ConnectionError:
            print(f"   ❌ 连接失败 - Django服务器可能未启动")
            api_results[endpoint] = {'status': 'connection_error'}
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            api_results[endpoint] = {'status': 'exception', 'error': str(e)}
    
    return api_results

def test_page_rendering():
    """测试页面渲染"""
    print("\n🔍 测试页面渲染...")
    
    base_url = "http://localhost:8000"
    pages = [
        '/live/',
        '/live/danmaku/',
        '/live/debug/',
    ]
    
    page_results = {}
    
    for page in pages:
        try:
            print(f"\n🌐 测试页面 {page}")
            response = requests.get(f"{base_url}{page}", timeout=10)
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                print(f"   页面大小: {len(content)} 字符")
                
                # 检查关键元素
                checks = {
                    'system_stats': 'system_stats' in content,
                    'active_rooms': 'active_rooms' in content,
                    'redis_status': 'redis_status' in content or 'Redis' in content,
                    'javascript': '<script>' in content,
                    'api_calls': 'fetch(' in content or 'ajax' in content or '$.get' in content,
                    'csrf_token': 'csrf' in content.lower(),
                }
                
                print(f"   内容检查: {checks}")
                page_results[page] = {'status': 'success', 'checks': checks, 'size': len(content)}
                
                # 检查是否有JavaScript错误
                if 'error' in content.lower() or 'exception' in content.lower():
                    print(f"   ⚠️ 页面可能包含错误信息")
                
            else:
                print(f"   ❌ 页面加载失败: {response.status_code}")
                page_results[page] = {'status': 'error', 'code': response.status_code}
                
        except Exception as e:
            print(f"   ❌ 页面请求失败: {e}")
            page_results[page] = {'status': 'exception', 'error': str(e)}
    
    return page_results

def test_django_context():
    """测试Django上下文数据"""
    print("\n🔍 测试Django视图上下文...")
    
    try:
        from django.test import Client
        client = Client()
        
        # 测试dashboard视图
        response = client.get('/live/')
        print(f"Dashboard状态码: {response.status_code}")
        
        if response.status_code == 200:
            # 检查上下文数据
            if hasattr(response, 'context'):
                context = response.context
                print(f"上下文变量: {list(context.keys()) if context else '无上下文'}")
                
                if context:
                    for key in ['system_stats', 'active_rooms', 'debug_info']:
                        if key in context:
                            value = context[key]
                            print(f"   {key}: {type(value)} = {str(value)[:100]}...")
                        else:
                            print(f"   {key}: 不存在")
            else:
                print("   ❌ 无法获取上下文数据")
        
        # 测试API视图
        api_response = client.get('/live/api/system/stats/')
        print(f"API状态码: {api_response.status_code}")
        
        if api_response.status_code == 200:
            try:
                api_data = api_response.json()
                print(f"API数据: {json.dumps(api_data, indent=2, ensure_ascii=False)[:200]}...")
            except:
                print("API响应不是有效的JSON")
        
    except Exception as e:
        print(f"❌ Django测试失败: {e}")

def main():
    print("🔧 网页问题诊断工具")
    print("=" * 50)
    
    # 1. 测试Django上下文
    test_django_context()
    
    # 2. 测试API端点
    api_results = test_api_endpoints()
    
    # 3. 测试页面渲染
    page_results = test_page_rendering()
    
    # 4. 分析结果
    print("\n📊 诊断结果分析:")
    print("-" * 30)
    
    # API分析
    api_success = sum(1 for r in api_results.values() if r.get('status') == 'success')
    print(f"API测试: {api_success}/{len(api_results)} 成功")
    
    for endpoint, result in api_results.items():
        if result.get('status') != 'success':
            print(f"   ❌ {endpoint}: {result.get('status', 'unknown')}")
    
    # 页面分析
    page_success = sum(1 for r in page_results.values() if r.get('status') == 'success')
    print(f"页面测试: {page_success}/{len(page_results)} 成功")
    
    for page, result in page_results.items():
        if result.get('status') == 'success':
            checks = result.get('checks', {})
            failed_checks = [k for k, v in checks.items() if not v]
            if failed_checks:
                print(f"   ⚠️ {page}: 缺少 {failed_checks}")
        else:
            print(f"   ❌ {page}: {result.get('status', 'unknown')}")
    
    # 修复建议
    print("\n💡 修复建议:")
    
    if api_success < len(api_results):
        print("1. 确保Django服务器正在运行: python manage.py runserver")
        print("2. 检查Redis连接状态")
    
    if page_success < len(page_results):
        print("3. 检查模板文件是否存在")
        print("4. 检查JavaScript代码是否正确")
        print("5. 查看浏览器开发者工具的Console和Network标签")

if __name__ == "__main__":
    main()