@echo off
chcp 65001 >nul
echo ========================================
echo Eco3S 前后端启动脚本
echo ========================================
echo.

echo [1/3] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)
echo ✓ Python环境正常

echo.
echo [2/3] 启动后端服务...
start "Eco3S Backend" cmd /k "cd /d %~dp0 && echo 正在启动后端服务... && python src\app.py"
timeout /t 3 >nul

echo.
echo [3/3] 启动前端服务...
cd frontend
if not exist node_modules (
    echo 首次运行，正在安装前端依赖...
    call npm install
)
start "Eco3S Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo ✓ 启动完成！
echo ========================================
echo.
echo 后端服务: http://localhost:5000
echo 前端服务: http://localhost:5173
echo.
echo 请在浏览器中访问前端地址开始使用
echo 按任意键关闭此窗口...
pause >nul
