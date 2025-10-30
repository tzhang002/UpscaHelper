# 安装:

### 依赖:

- `uv`
- `python>=3.10` 
- 必须有独立显卡（推荐N卡，A卡也可，少量的核显也可，以upscayl-ncnn项目的支持为准https://github.com/upscayl/upscayl-ncnn）

### 步骤:

1. 克隆整个项目:

   `git clone https://github.com/tzhang002/UpscaHelper.git`

2. 进入项目目录，下载文件https://github.com/tzhang002/UpscaHelper/releases/download/v1.0/models.zip并解压到项目目录中
3. 更新依赖: `uv sync`
4. 下载https://github.com/tzhang002/upscayl-ncnn/releases/tag/v1.0中的对应操作系统的预编译文件
5. 将文件移到添加到环境变量的目录中(Linux例如放入/usr/local/bin/)
6. `uv run main.py` 即可看到UI界面

### 使用方法:

- 输入目录列表：用于添加待处理图片的目录，可以添加多个
- 输出基目录：用于存放处理后的图片，设置一个目录即可
- 缩放比例及格式可以根据实际情况进行选择
- 模型名称：和models目录对应（目录中的名字不要随便修改，模型来源是upscayl项目）
- 生成PDF：默认勾选，可以取消。勾选的话会将整个目录的图片合成一个PDF,多个目录则会对应生成多个PDF
- 开始处理：点击后开始处理
- 停止处理：点击后停止处理

### 注意事项:

- 本项目仅用于学习交流，请勿用于商业用途
- 本项目中的模型来源于upscayl项目，本人在upscayl项目的基础上进行了修改，以适应本项目的需求
- 本项目中的代码仅供参考，请勿直接用于生产环境