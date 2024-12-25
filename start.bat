@echo off
if exist localshare.py (
    python localshare.py
) else (
    echo localshare.py 没有此文件
)
start http://localhost:5000