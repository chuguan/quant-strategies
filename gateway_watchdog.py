"""
Clawbot（Hermes Gateway）看门狗
功能: 每分钟检测Gateway是否存活，挂了自动重启
"""
import subprocess, os, time, sys
from datetime import datetime

HERMES_HOME = os.path.expanduser('~/AppData/Local/hermes')
GATEWAY_CMD = os.path.join(HERMES_HOME, 'gateway-service', 'Hermes_Gateway.cmd')
LOG_FILE = os.path.join(HERMES_HOME, 'logs', 'gateway_watchdog.log')

def log(msg):
    t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{t}] {msg}'
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def is_gateway_running():
    """检测Hermes Gateway是否在运行"""
    try:
        # Windows: 检查进程
        r = subprocess.run(
            ['wmic', 'process', 'where', 
             "name='pythonw.exe'", 
             'get', 'CommandLine', '/format:csv'],
            capture_output=True, text=True, timeout=10
        )
        return 'gateway run' in r.stdout or 'hermes_cli.main gateway' in r.stdout
    except:
        # 备选：用tasklist
        try:
            r = subprocess.run(
                ['tasklist', '/fi', 'IMAGENAME eq pythonw.exe', '/nh'],
                capture_output=True, text=True, timeout=10
            )
            if 'pythonw.exe' not in r.stdout:
                return False
            # 进一步检查是否是gateway
            r2 = subprocess.run(
                ['wmic', 'process', 'where', "name='pythonw.exe'", 'get', 'ProcessId'],
                capture_output=True, text=True, timeout=10
            )
            pids = [p.strip() for p in r2.stdout.split('\n') if p.strip().isdigit()]
            for pid in pids:
                try:
                    cmd = subprocess.run(
                        ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine'],
                        capture_output=True, text=True, timeout=5
                    )
                    if 'gateway run' in cmd.stdout:
                        return True
                except:
                    pass
            return False
        except:
            return False

def restart_gateway():
    """重启Gateway"""
    log('⚠️ Gateway已停止，正在重启...')
    try:
        # 用start /B以后台方式运行
        subprocess.Popen(
            ['cmd', '/c', 'start', '/B', GATEWAY_CMD],
            shell=True, cwd=os.path.dirname(GATEWAY_CMD)
        )
        log('✅ 重启命令已发送，等待3秒确认...')
        time.sleep(3)
        if is_gateway_running():
            log('✅ Gateway启动成功！')
            return True
        else:
            log('❌ Gateway启动失败，重试中...')
            time.sleep(5)
            # 直接py启动
            venv_python = os.path.join(HERMES_HOME, 'hermes-agent', 'venv', 'Scripts', 'pythonw.exe')
            subprocess.Popen(
                [venv_python, '-m', 'hermes_cli.main', 'gateway', 'run'],
                shell=True
            )
            time.sleep(5)
            if is_gateway_running():
                log('✅ 二次启动成功！')
                return True
            else:
                log('❌ 二次启动也失败，需要人工检查')
                return False
    except Exception as e:
        log(f'❌ 重启异常: {e}')
        return False

def main():
    log('=== Gateway看门狗启动 ===')
    
    running = is_gateway_running()
    if running:
        log('✅ Gateway正常运行中')
        return
    
    # 挂了，重启
    restart_gateway()

if __name__ == '__main__':
    main()
