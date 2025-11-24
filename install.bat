@echo off
echo 正在安装依赖...
pip uninstall pyzbar -y
pip install -r requirements.txt
echo.
echo 安装完成！现在可以运行: python app.py
pause

