import sys
import os
import subprocess
import glob
import re
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                               QLineEdit, QPushButton, QComboBox, QSpinBox, 
                               QCheckBox, QTextEdit, QFileDialog, QMessageBox,
                               QProgressBar, QSplitter, QListWidget, QListWidgetItem)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QPalette, QColor

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Image, PageBreak
    from reportlab.lib.utils import ImageReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("警告: 未安装reportlab库，PDF生成功能将不可用。请使用 'pip install reportlab' 安装。")


def natural_sort_key(s):
    """
    自然排序键函数，用于对包含数字的字符串进行排序
    例如：wmakx1263DL_10.jpg -> ['wmakx', 1263, 'DL_', 10, '.jpg']
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]


class UpscaylWorker(QThread):
    """工作线程，用于执行Upscayl命令"""
    
    # 信号定义
    output_signal = Signal(str)
    progress_signal = Signal(int, int)  # 当前进度, 总任务数
    finished_signal = Signal(bool, str)
    directory_finished = Signal(str, str)  # 目录名, 输出目录
    
    def __init__(self, command, directories, output_base, args):
        super().__init__()
        self.command = command
        self.directories = directories
        self.output_base = output_base
        self.args = args
        self.is_running = True
        
    def run(self):
        try:
            total_dirs = len(self.directories)
            
            for i, input_dir in enumerate(self.directories):
                if not self.is_running:
                    break
                    
                # 为每个输入目录创建对应的输出目录
                dir_name = Path(input_dir).name
                output_dir = Path(self.output_base) / dir_name
                output_dir.mkdir(parents=True, exist_ok=True)
                
                self.output_signal.emit(f"处理目录 {i+1}/{total_dirs}: {input_dir}")
                self.progress_signal.emit(i, total_dirs)
                
                # 构建完整的命令
                dir_args = self.args.copy()
                
                # 替换输入输出路径
                for j, arg in enumerate(dir_args):
                    if arg == "-i" and j+1 < len(dir_args):
                        dir_args[j+1] = input_dir
                    elif arg == "-o" and j+1 < len(dir_args):
                        dir_args[j+1] = str(output_dir)
                
                full_command = [self.command] + dir_args
                self.output_signal.emit(f"执行命令: {' '.join(full_command)}\n")
                
                # 执行命令
                process = subprocess.Popen(
                    full_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # 读取输出
                for line in process.stdout:
                    if self.is_running:
                        self.output_signal.emit(line)
                    else:
                        process.terminate()
                        break
                        
                # 等待进程结束
                process.wait()
                
                if process.returncode == 0:
                    self.output_signal.emit(f"✓ 目录处理完成: {input_dir}\n")
                    self.directory_finished.emit(input_dir, str(output_dir))
                else:
                    self.output_signal.emit(f"✗ 目录处理失败: {input_dir}, 返回码: {process.returncode}\n")
            
            if self.is_running:
                self.finished_signal.emit(True, f"所有目录处理完成！共处理了 {total_dirs} 个目录。")
            else:
                self.finished_signal.emit(False, "处理被用户中断")
                
        except Exception as e:
            self.finished_signal.emit(False, f"执行错误: {str(e)}")
            
    def stop(self):
        self.is_running = False


class UpscaylGUI(QMainWindow):
    """Upscayl图形界面主窗口"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Upscayl 图形界面 v1.0 - 多目录处理")
        self.setMinimumSize(900, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：参数设置
        settings_widget = self.create_settings_widget()
        splitter.addWidget(settings_widget)
        
        # 下半部分：输出日志
        log_widget = self.create_log_widget()
        splitter.addWidget(log_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 300])
        
        main_layout.addWidget(splitter)
        
        # 底部：控制按钮
        control_layout = self.create_control_buttons()
        main_layout.addLayout(control_layout)
        
    def create_settings_widget(self):
        """创建参数设置区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 基本参数组
        basic_group = QGroupBox("基本参数")
        basic_layout = QGridLayout(basic_group)
        
        # 输入目录列表
        basic_layout.addWidget(QLabel("输入目录列表:"), 0, 0)
        self.directories_list = QListWidget()
        self.directories_list.setMaximumHeight(100)
        basic_layout.addWidget(self.directories_list, 0, 1, 1, 2)
        
        # 目录操作按钮
        dir_buttons_layout = QHBoxLayout()
        self.add_dir_btn = QPushButton("添加目录")
        self.add_dir_btn.clicked.connect(self.add_directory)
        self.remove_dir_btn = QPushButton("移除选中目录")
        self.remove_dir_btn.clicked.connect(self.remove_directory)
        self.clear_dirs_btn = QPushButton("清空目录列表")
        self.clear_dirs_btn.clicked.connect(self.clear_directories)
        
        dir_buttons_layout.addWidget(self.add_dir_btn)
        dir_buttons_layout.addWidget(self.remove_dir_btn)
        dir_buttons_layout.addWidget(self.clear_dirs_btn)
        dir_buttons_layout.addStretch()
        
        basic_layout.addLayout(dir_buttons_layout, 1, 1, 1, 2)
        
        # 输出基目录
        basic_layout.addWidget(QLabel("输出基目录:"), 2, 0)
        self.output_base_edit = QLineEdit()
        basic_layout.addWidget(self.output_base_edit, 2, 1)
        self.output_base_btn = QPushButton("浏览...")
        self.output_base_btn.clicked.connect(self.browse_output_base)
        basic_layout.addWidget(self.output_base_btn, 2, 2)
        
        # 模型缩放
        basic_layout.addWidget(QLabel("模型缩放:"), 3, 0)
        self.model_scale_combo = QComboBox()
        self.model_scale_combo.addItems(["2", "3", "4"])
        self.model_scale_combo.setCurrentText("2")
        basic_layout.addWidget(self.model_scale_combo, 3, 1)
        
        # 输出缩放
        basic_layout.addWidget(QLabel("输出缩放:"), 4, 0)
        self.output_scale_combo = QComboBox()
        self.output_scale_combo.addItems(["2", "3", "4"])
        self.output_scale_combo.setCurrentText("2")
        basic_layout.addWidget(self.output_scale_combo, 4, 1)
        
        # 输出格式
        basic_layout.addWidget(QLabel("输出格式:"), 5, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "webp", "保持原格式"])
        self.format_combo.setCurrentText("保持原格式")
        basic_layout.addWidget(self.format_combo, 5, 1)
        
        layout.addWidget(basic_group)
        
        # 高级参数组
        advanced_group = QGroupBox("高级参数")
        advanced_layout = QGridLayout(advanced_group)
        
        # 模型路径
        advanced_layout.addWidget(QLabel("模型路径:"), 0, 0)
        self.model_path_edit = QLineEdit("models")
        advanced_layout.addWidget(self.model_path_edit, 0, 1)
        self.model_path_btn = QPushButton("浏览...")
        self.model_path_btn.clicked.connect(self.browse_model_path)
        advanced_layout.addWidget(self.model_path_btn, 0, 2)
        
        # 模型名称
        advanced_layout.addWidget(QLabel("模型名称:"), 1, 0)
        self.model_name_combo = QComboBox()
        self.model_name_combo.addItems([
            "digital-art-4x",
            "high-fidelity-4x", 
            "remacri-4x",
            "ultramix-balanced-4x",
            "ultrasharp-4x",
            "upscayl-lite-4x",
            "upscayl-standard-4x"
        ])
        self.model_name_combo.setEditable(True)
        advanced_layout.addWidget(self.model_name_combo, 1, 1)
        
        # 调整尺寸
        advanced_layout.addWidget(QLabel("调整尺寸:"), 2, 0)
        self.resize_edit = QLineEdit()
        self.resize_edit.setPlaceholderText("例如: 1920x1080")
        advanced_layout.addWidget(self.resize_edit, 2, 1)
        
        # 宽度
        advanced_layout.addWidget(QLabel("宽度:"), 3, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 10000)
        self.width_spin.setSpecialValueText("默认")
        advanced_layout.addWidget(self.width_spin, 3, 1)
        
        # 压缩
        advanced_layout.addWidget(QLabel("压缩质量:"), 4, 0)
        self.compress_spin = QSpinBox()
        self.compress_spin.setRange(0, 100)
        self.compress_spin.setValue(0)
        advanced_layout.addWidget(self.compress_spin, 4, 1)
        
        # 瓦片大小
        advanced_layout.addWidget(QLabel("瓦片大小:"), 5, 0)
        self.tile_size_edit = QLineEdit("0")
        self.tile_size_edit.setPlaceholderText("0=自动, 或如 0,0,0 用于多GPU")
        advanced_layout.addWidget(self.tile_size_edit, 5, 1)
        
        # GPU ID
        advanced_layout.addWidget(QLabel("GPU ID:"), 6, 0)
        self.gpu_id_edit = QLineEdit("auto")
        advanced_layout.addWidget(self.gpu_id_edit, 6, 1)
        
        # 线程数
        advanced_layout.addWidget(QLabel("线程数:"), 7, 0)
        self.threads_edit = QLineEdit("1:2:2")
        self.threads_edit.setPlaceholderText("load:proc:save")
        advanced_layout.addWidget(self.threads_edit, 7, 1)
        
        # 选项复选框
        option_layout = QHBoxLayout()
        self.tta_checkbox = QCheckBox("TTA模式")
        self.verbose_checkbox = QCheckBox("详细输出")
        self.pdf_checkbox = QCheckBox("生成PDF")
        self.pdf_checkbox.setChecked(True)
        option_layout.addWidget(self.tta_checkbox)
        option_layout.addWidget(self.verbose_checkbox)
        option_layout.addWidget(self.pdf_checkbox)
        option_layout.addStretch()
        advanced_layout.addLayout(option_layout, 8, 0, 1, 3)
        
        layout.addWidget(advanced_group)
        
        return widget
        
    def create_log_widget(self):
        """创建日志输出区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("处理日志:"))
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.log_text.setFont(font)
        
        # 设置深色主题
        palette = self.log_text.palette()
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        self.log_text.setPalette(palette)
        
        layout.addWidget(self.log_text)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return widget
        
    def create_control_buttons(self):
        """创建控制按钮"""
        layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始处理")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.clicked.connect(self.clear_log)
        
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.clear_btn)
        layout.addStretch()
        
        return layout
        
    def add_directory(self):
        """添加目录到列表"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "选择输入目录"
        )
        if dir_path and dir_path not in [self.directories_list.item(i).text() for i in range(self.directories_list.count())]:
            self.directories_list.addItem(dir_path)
            
    def remove_directory(self):
        """移除选中的目录"""
        current_row = self.directories_list.currentRow()
        if current_row >= 0:
            self.directories_list.takeItem(current_row)
            
    def clear_directories(self):
        """清空目录列表"""
        self.directories_list.clear()
            
    def browse_output_base(self):
        """浏览输出基目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出基目录"
        )
        if dir_path:
            self.output_base_edit.setText(dir_path)
            
    def browse_model_path(self):
        """浏览模型目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择模型目录",
            self.model_path_edit.text() or ""
        )
        if dir_path:
            self.model_path_edit.setText(dir_path)
            
    def log_message(self, message):
        """添加日志消息"""
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        
    def validate_inputs(self):
        """验证输入参数"""
        if self.directories_list.count() == 0:
            QMessageBox.warning(self, "输入错误", "请至少添加一个输入目录")
            return False
            
        if not self.output_base_edit.text().strip():
            QMessageBox.warning(self, "输出错误", "请输入输出基目录路径")
            return False
            
        # 检查所有目录是否存在
        for i in range(self.directories_list.count()):
            dir_path = Path(self.directories_list.item(i).text())
            if not dir_path.exists():
                QMessageBox.warning(self, "输入错误", f"目录不存在: {dir_path}")
                return False
                
        return True
        
    def build_arguments(self):
        """构建命令行参数"""
        args = []
        
        # 基本参数
        # 注意：输入输出路径会在工作线程中动态设置
        args.extend(["-i", "PLACEHOLDER_INPUT"])
        args.extend(["-o", "PLACEHOLDER_OUTPUT"])
        args.extend(["-z", self.model_scale_combo.currentText()])
        args.extend(["-s", self.output_scale_combo.currentText()])
        
        # 模型参数
        args.extend(["-m", self.model_path_edit.text()])
        args.extend(["-n", self.model_name_combo.currentText()])
        
        # 可选参数
        if self.resize_edit.text().strip():
            args.extend(["-r", self.resize_edit.text()])
            
        if self.width_spin.value() > 0:
            args.extend(["-w", str(self.width_spin.value())])
            
        if self.compress_spin.value() > 0:
            args.extend(["-c", str(self.compress_spin.value())])
            
        if self.tile_size_edit.text().strip() and self.tile_size_edit.text() != "0":
            args.extend(["-t", self.tile_size_edit.text()])
            
        if self.gpu_id_edit.text().strip() and self.gpu_id_edit.text() != "auto":
            args.extend(["-g", self.gpu_id_edit.text()])
            
        if self.threads_edit.text().strip() and self.threads_edit.text() != "1:2:2":
            args.extend(["-j", self.threads_edit.text()])
            
        # 输出格式
        if self.format_combo.currentText() != "保持原格式":
            args.extend(["-f", self.format_combo.currentText()])
            
        # 布尔选项
        if self.tta_checkbox.isChecked():
            args.append("-x")
            
        if self.verbose_checkbox.isChecked():
            args.append("-v")
            
        return args
        
    def create_pdf_from_directory(self, input_dir, output_dir):
        """将目录中的图片按自然排序顺序合并成PDF，每页尺寸精确匹配图片尺寸"""
        try:
            if not PDF_SUPPORT:
                self.log_message("警告: 未安装reportlab库，无法生成PDF")
                return False
                
            # 获取目录中所有图片文件
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp', '*.tiff']
            image_files = []
            for ext in image_extensions:
                image_files.extend(glob.glob(os.path.join(output_dir, ext)))
                image_files.extend(glob.glob(os.path.join(output_dir, ext.upper())))

            # 使用自然排序对文件名进行排序
            image_files.sort(key=natural_sort_key)

            if not image_files:
                self.log_message(f"警告: 目录 {output_dir} 中没有找到图片文件")
                return False

            # 创建PDF文件名
            dir_name = Path(input_dir).name
            pdf_path = Path(self.output_base_edit.text()) / f"{dir_name}.pdf"

            self.log_message(f"生成PDF: {pdf_path}，包含 {len(image_files)} 张图片")

            # 创建自定义页面尺寸的PDF
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from PIL import Image

            pdf = canvas.Canvas(str(pdf_path))

            for i, img_path in enumerate(image_files):
                try:
                    self.log_message(f"  处理图片 {i+1}/{len(image_files)}: {Path(img_path).name}")

                    # 获取图片尺寸
                    with Image.open(img_path) as img:
                        img_width, img_height = img.size

                    # 设置PDF页面尺寸为图片尺寸（以点为单位的尺寸，1点=1/72英寸）
                    # 假设图片为72DPI，这样像素尺寸就直接对应点尺寸
                    page_width = img_width
                    page_height = img_height

                    self.log_message(f"    图片尺寸: {img_width} x {img_height} 像素")
                    self.log_message(f"    PDF页面尺寸: {page_width} x {page_height} 点")

                    # 设置页面尺寸
                    pdf.setPageSize((page_width, page_height))

                    # 将图片绘制到页面上，完全填满页面
                    pdf.drawImage(img_path, 0, 0, width=page_width, height=page_height)

                    # 如果还有更多图片，添加新页面
                    if i < len(image_files) - 1:
                        pdf.showPage()

                    self.log_message("    ✓ 图片已添加到PDF")

                except Exception as e:
                    self.log_message(f"  错误: 无法处理图片 {img_path}: {str(e)}")
                    continue

            # 保存PDF
            pdf.save()

            # 验证生成的PDF
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
                self.log_message(f"✓ PDF生成成功: {pdf_path} ({file_size:.2f} MB)")
                self.log_message("✓ 所有图片已按原始尺寸插入PDF页面")
                return True
            else:
                self.log_message("✗ PDF文件未成功创建")
                return False

        except Exception as e:
            self.log_message(f"✗ PDF生成失败: {str(e)}")
            return False
        
    def start_processing(self):
        """开始处理"""
        if not self.validate_inputs():
            return
            
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "处理中", "当前有任务正在运行，请等待完成或停止")
            return
            
        # 获取目录列表
        directories = [self.directories_list.item(i).text() for i in range(self.directories_list.count())]
        output_base = self.output_base_edit.text()
        
        # 构建命令
        upscayl_bin = "upscayl-bin"  # 假设在系统PATH中，或需要完整路径
        args = self.build_arguments()
        
        # 创建并启动工作线程
        self.worker = UpscaylWorker(upscayl_bin, directories, output_base, args)
        self.worker.output_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.directory_finished.connect(self.on_directory_finished)
        
        self.worker.start()
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(directories))
        self.progress_bar.setValue(0)
        
        self.log_message(f"🚀 开始处理 {len(directories)} 个目录...")
        
    def update_progress(self, current, total):
        """更新进度条"""
        self.progress_bar.setValue(current)
        
    def on_directory_finished(self, input_dir, output_dir):
        """单个目录处理完成"""
        self.log_message(f"目录处理完成: {input_dir} -> {output_dir}")
        
        # 如果启用了PDF生成，则创建PDF
        if self.pdf_checkbox.isChecked():
            self.log_message("开始生成PDF...")
            self.create_pdf_from_directory(input_dir, output_dir)
        
    def stop_processing(self):
        """停止处理"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.log_message("⏹️ 处理已停止")
            
    def processing_finished(self, success, message):
        """处理完成回调"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self.log_message(message)
        
        if success:
            QMessageBox.information(self, "完成", "所有目录处理完成！")
        else:
            QMessageBox.warning(self, "错误", "处理过程中出现错误，请查看日志")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    window = UpscaylGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
