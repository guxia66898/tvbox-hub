"""tvbox-hub 入口：python run.py --config config.json"""
import os
import sys

# 显式把项目根加入 sys.path，兼容 PYTHONSAFEPATH 等收紧环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hub.run import main

if __name__ == '__main__':
    main()
