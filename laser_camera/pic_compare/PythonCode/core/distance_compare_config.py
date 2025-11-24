# pic_compare/PythonCode/core/distance_compare_config.py

# 黄线在画面中的高度比例（0~1）
YELLOW_LINE_Y_RATIO = 0.90

# 判断“踩在线上”的容差（相对于高度的比例）
ON_LINE_BAND_RATIO = 0.02   # ±2%

# 进入危险区再往里一点的裕度
INSIDE_MARGIN_RATIO = 0.03  # 3%

# 只在画面下半部分找脚（减少假目标）
ROI_BOTTOM_RATIO = 0.60