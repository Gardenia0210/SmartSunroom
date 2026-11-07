请将待分析的照片放在此文件夹，然后通过 CLI 运行：

```powershell
cd E:\SFK\Project3\SmartSunroom

python -m src.cli analyze ^
  --image data/photos/你的照片.jpg ^
  --age 25 ^
  --young-mode relaxation ^
  --light UVB ^
  --ns-angle 45 ^
  --ew-zero 30
```

支持格式：`.jpg` `.jpeg` `.png` `.bmp`

输出会写入 `data/outputs/`（网格 CSV、可视化图、平行/垂直玻璃序号）。
