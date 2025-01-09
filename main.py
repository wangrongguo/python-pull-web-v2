import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QTextEdit,
                            QTableWidget, QTableWidgetItem, QLabel, QFileDialog, QMenu)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtGui import QIcon
import pandas as pd
from element_selector import ElementSelector
from PyQt5.QtCore import QTimer, QObject, pyqtSlot
import json
import os

class WebScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.data = []
        self.selector_mode = False
        
        # 设置应用图标
        self.setWindowIcon(QIcon('images/icon_app.png'))
        
        # 设置WebChannel
        self.channel = QWebChannel()
        self.selector = ElementSelector(self.browser, self.data_table, self.status_bar)
        self.channel.registerObject('elementSelector', self.selector)
        self.browser.page().setWebChannel(self.channel)
        
        # 在页面加载完成后初始化WebChannel
        self.browser.loadFinished.connect(self.onLoadFinished)
        
    def onLoadFinished(self, ok):
        if ok:
            print("页面加载完成，开始初始化WebChannel")
            # 先注入QWebChannel.js
            self.browser.page().runJavaScript("""
                if (!window.QWebChannel) {
                    var script = document.createElement('script');
                    script.src = 'qrc:///qtwebchannel/qwebchannel.js';
                    document.head.appendChild(script);
                }
            """)
            
            # 等待一段时间后初始化WebChannel
            QTimer.singleShot(500, self.initializeWebChannel)
        else:
            print("页面加载失败")
            
    def initializeWebChannel(self):
        js = """
        (function() {
            if (typeof QWebChannel === 'undefined') {
                console.error('QWebChannel not loaded yet');
                return;
            }
            
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.qt = channel.objects;
                console.log('QWebChannel initialized');
                
                // 添加样式
                if (!document.getElementById('element-selector-style')) {
                    const style = document.createElement('style');
                    style.id = 'element-selector-style';
                    style.textContent = `
                        .element-selector-highlight {
                            outline: 2px solid rgba(255, 165, 0, 0.5) !important;
                            outline-offset: -2px !important;
                            cursor: pointer !important;
                            background-color: rgba(255, 255, 0, 0.1) !important;
                        }
                    `;
                    document.head.appendChild(style);
                }
                
                // 添加全局函数
                window.getFullPath = function(el) {
                    if (!el || !el.nodeType) return '';
                    let path = [];
                    while (el && el.nodeType === Node.ELEMENT_NODE) {
                        let selector = el.nodeName.toLowerCase();
                        if (el.id) {
                            selector += '#' + el.id;
                            path.unshift(selector);
                            break;
                        } else {
                            let sib = el, nth = 1;
                            while (sib.previousElementSibling) {
                                sib = sib.previousElementSibling;
                                if (sib.nodeName.toLowerCase() === selector) nth++;
                            }
                            if (nth !== 1) selector += ":nth-of-type("+nth+")";
                        }
                        path.unshift(selector);
                        el = el.parentNode;
                    }
                    return path.join(' > ');
                };
            });
        })();
        """
        self.browser.page().runJavaScript(js)
        print("WebChannel初始化完成")
        
    def checkWebChannelStatus(self):
        js = """
        (function() {
            if (window.qt && window.qt.elementSelector) {
                console.log('QWebChannel 状态检查: 已初始化');
                return true;
            } else {
                console.log('QWebChannel 状态检查: 未初始化');
                return false;
            }
        })();
        """
        def callback(result):
            if not result:
                print("QWebChannel未正确初始化，尝试重新初始化...")
                self.onLoadFinished(True)
                
        self.browser.page().runJavaScript(js, callback)
        
    def initUI(self):
        # 主窗口设置
        self.setWindowTitle('网页数据抓取工具')
        self.setGeometry(100, 100, 1200, 800)
        
        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        
        # 左侧面板（网页预览）
        left_panel = QVBoxLayout()
        
        # URL输入栏
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入网页URL...")
        url_layout.addWidget(self.url_input)
        
        self.preview_btn = QPushButton("预览")
        self.preview_btn.setIcon(QIcon('images/icon_preview.png'))
        self.preview_btn.clicked.connect(self.load_url)
        url_layout.addWidget(self.preview_btn)
        
        left_panel.addLayout(url_layout)
        
        # 网页预览窗口
        self.browser = QWebEngineView()
        self.browser.setPage(QWebEnginePage())
        
        # 启用必要的设置
        settings = self.browser.page().settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.XSSAuditingEnabled, False)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, False)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        
        # 设置自定义头部
        profile = self.browser.page().profile()
        profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        left_panel.addWidget(self.browser)
        
        # 右侧面板（数据展示）
        right_panel = QVBoxLayout()
        
        # 数据展示区域
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(1)  # 只显示内容列
        self.data_table.setHorizontalHeaderLabels(['内容'])
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)  # 整行选择
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 禁止编辑
        self.data_table.setContextMenuPolicy(Qt.CustomContextMenu)  # 启用自定义右键菜单
        self.data_table.customContextMenuRequested.connect(self.show_context_menu)  # 连接右键菜单信号
        # 设置表格列宽自动调整
        self.data_table.horizontalHeader().setStretchLastSection(True)
        # 设置表格行高
        self.data_table.verticalHeader().setDefaultSectionSize(30)  # 设置默认行高
        # 设置表格样式
        self.data_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QTableWidget::item:selected {
                background-color: #e6f3ff;
                color: black;
            }
        """)
        right_panel.addWidget(self.data_table)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        # 设置按钮样式
        button_style = """
            QPushButton {
                padding: 8px 15px 8px 35px;  /* 左侧增加padding以适应图标 */
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                min-width: 100px;  /* 增加最小宽度 */
                text-align: left;  /* 文字左对齐 */
                icon-size: 16px;  /* 设置图标大小 */
            }
            QPushButton:hover {
                background-color: #e6f3ff;
            }
            QPushButton:pressed {
                background-color: #cce6ff;
            }
            QPushButton:checked {
                background-color: #cce6ff;
                border-color: #99ccff;
            }
        """
        
        # 相似度设置布局
        similarity_layout = QHBoxLayout()
        similarity_label = QLabel("相似度阈值:")
        similarity_layout.addWidget(similarity_label)
        
        self.similarity_input = QLineEdit()
        self.similarity_input.setPlaceholderText("0.67")
        self.similarity_input.setText("0.67")  # 默认值
        self.similarity_input.setMaximumWidth(60)
        self.similarity_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        similarity_layout.addWidget(self.similarity_input)
        
        right_panel.addLayout(similarity_layout)
        
        self.select_btn = QPushButton("选择模式")
        self.select_btn.setIcon(QIcon('images/icon_select.png'))
        self.select_btn.setCheckable(True)
        self.select_btn.setStyleSheet(button_style)
        self.select_btn.clicked.connect(self.toggle_select_mode)
        btn_layout.addWidget(self.select_btn)
        
        self.match_btn = QPushButton("匹配")
        self.match_btn.setIcon(QIcon('images/icon_match.png'))
        self.match_btn.setStyleSheet(button_style)
        self.match_btn.clicked.connect(self.match_elements)
        btn_layout.addWidget(self.match_btn)
        
        self.save_btn = QPushButton("保存数据")
        self.save_btn.setIcon(QIcon('images/icon_save.png'))
        self.save_btn.setStyleSheet(button_style)
        self.save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(self.save_btn)
        
        self.next_btn = QPushButton("下一页")
        self.next_btn.setIcon(QIcon('images/icon_next.png'))
        self.next_btn.setStyleSheet(button_style)
        self.next_btn.clicked.connect(self.next_page)
        btn_layout.addWidget(self.next_btn)
        
        right_panel.addLayout(btn_layout)
        
        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("""
            QLabel {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                min-height: 20px;
            }
        """)
        self.status_bar.setWordWrap(True)  # 允许文本换行
        right_panel.addWidget(self.status_bar)
        
        # 组合左右面板
        main_layout.addLayout(left_panel, 2)
        main_layout.addLayout(right_panel, 1)
        
    def load_url(self):
        url = self.url_input.text()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            print(f"开始加载URL: {url}")
            self.browser.setUrl(QUrl(url))
            self.status_bar.setText(f"正在加载: {url}")
            
    def save_data(self):
        if not self.selector.selected_elements:
            self.status_bar.setText("没有数据可保存")
            return
            
        # 生成带时间戳的默认文件名
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"scraped_data_{timestamp}"
        
        options = QFileDialog.Options()
        file_name, file_type = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            default_filename,
            "CSV Files (*.csv);;JSON Files (*.json);;Excel Files (*.xlsx)",
            options=options
        )
        
        if file_name:
            try:
                # 准备数据
                data = []
                for element in self.selector.selected_elements:
                    data.append({
                        'text': element['text'],
                        'selector': element['selector'],
                        'href': element.get('href', '')
                    })
                
                # 根据文件类型保存
                if file_name.endswith('.csv'):
                    df = pd.DataFrame(data)
                    df.to_csv(file_name, index=False, encoding='utf-8-sig')  # 使用带BOM的UTF-8编码
                elif file_name.endswith('.json'):
                    with open(file_name, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                elif file_name.endswith('.xlsx'):
                    df = pd.DataFrame(data)
                    df.to_excel(file_name, index=False)
                
                self.status_bar.setText(f"数据已保存到: {file_name}")
            except Exception as e:
                self.status_bar.setText(f"保存失败: {str(e)}")
                print(f"保存数据时出错: {str(e)}")
                
    def next_page(self):
        self.status_bar.setText("下一页功能待实现")
        
    def toggle_select_mode(self):
        if self.select_btn.isChecked():
            # 确保浏览器窗口已加载完成
            if self.browser.page():
                self.selector.enable_selector_mode()
                print("选择模式已启用")
        else:
            self.selector.disable_selector_mode()
            print("选择模式已禁用")
                
    def check_mouse_position(self):
        if self.browser.page() and self.select_btn.isChecked():
            # 获取当前鼠标位置
            pos = self.browser.mapFromGlobal(self.browser.cursor().pos())
            if self.browser.rect().contains(pos):
                self.selector.highlight_element_at(pos)
                print(f"Mouse position checked: {pos.x()}, {pos.y()}")
        
    def show_context_menu(self, pos):
        menu = QMenu()
        delete_action = menu.addAction("删除")
        action = menu.exec_(self.data_table.mapToGlobal(pos))
        
        if action == delete_action:
            self.delete_selected_rows()
            
    def delete_selected_rows(self):
        rows = set()
        for item in self.data_table.selectedItems():
            rows.add(item.row())
        
        # 从大到小删除行，避免索引变化
        for row in sorted(rows, reverse=True):
            self.data_table.removeRow(row)
            if row < len(self.selector.selected_elements):
                self.selector.selected_elements.pop(row)
                
    def truncate_text(self, text, max_length=50):
        """截断文本，保留指定长度"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def update_status(self, text):
        """更新状态栏显示"""
        self.status_bar.setText(self.truncate_text(text))

    def match_elements(self):
        if not self.selector.selected_elements:
            self.update_status("没有选择器可匹配")
            return
            
        # 获取用户输入的相似度阈值
        try:
            threshold = float(self.similarity_input.text())
            if not 0 <= threshold <= 1:
                self.update_status("相似度阈值必须在0到1之间")
                return
        except ValueError:
            self.update_status("请输入有效的相似度阈值（0-1之间的小数）")
            return
            
        # 收集所有选择器和类名
        selectors_info = []
        for item in self.selector.selected_elements:
            selector = item['selector']
            class_name = ''
            if 'className' in item:
                class_name = item['className']
            selectors_info.append({
                'selector': selector,
                'className': class_name
            })
        
        # 构建JavaScript代码来匹配元素
        js = """
        (function() {
            let results = [];
            let selectorsInfo = %s;
            let SIMILARITY_THRESHOLD = %f;  // 从Python传入相似度阈值
            
            // 计算两个选择器的相似度
            function calculateSelectorSimilarity(selector1, selector2) {
                let parts1 = selector1.split('>').map(s => s.trim());
                let parts2 = selector2.split('>').map(s => s.trim());
                
                // 计算相同部分的数量
                let commonParts = 0;
                let totalParts = Math.max(parts1.length, parts2.length);
                
                // 从后往前比较，因为后面的选择器部分通常更重要
                for (let i = 1; i <= Math.min(parts1.length, parts2.length); i++) {
                    if (parts1[parts1.length - i] === parts2[parts2.length - i]) {
                        commonParts++;
                    } else {
                        break;  // 一旦不同就停止比较
                    }
                }
                
                return commonParts / totalParts;
            }
            
            // 计算两个类名字符串的相似度
            function calculateClassSimilarity(classes1, classes2) {
                if (!classes1 || !classes2) return 0;
                
                // 将类名字符串转换为数组并排序
                let set1 = new Set(classes1.split(/\\s+/).filter(c => c.length > 0).sort());
                let set2 = new Set(classes2.split(/\\s+/).filter(c => c.length > 0).sort());
                
                if (set1.size === 0 || set2.size === 0) return 0;
                
                // 计算交集
                let intersection = new Set([...set1].filter(x => set2.has(x)));
                
                // 计算相似度
                return intersection.size / Math.max(set1.size, set2.size);
            }
            
            // 遍历所有元素
            function getAllElements() {
                return document.getElementsByTagName('*');
            }
            
            let elements = getAllElements();
            for (let element of elements) {
                try {
                    let elementSelector = getFullPath(element);
                    let elementClasses = element.className;
                    let text = (element.innerText || element.textContent || '').trim();
                    
                    if (!text) continue;  // 跳过没有文本的元素
                    
                    // 检查是否与任何一个选择器匹配
                    for (let info of selectorsInfo) {
                        let selectorSimilarity = calculateSelectorSimilarity(elementSelector, info.selector);
                        let classSimilarity = calculateClassSimilarity(elementClasses, info.className);
                        
                        // 新的匹配逻辑：选择器或类名超过阈值即匹配
                        if (selectorSimilarity >= SIMILARITY_THRESHOLD || classSimilarity >= SIMILARITY_THRESHOLD) {
                            results.push({
                                selector: elementSelector,
                                text: text,
                                href: element.href || '',
                                selectorSimilarity: selectorSimilarity,
                                classSimilarity: classSimilarity,
                                totalSimilarity: Math.max(selectorSimilarity, classSimilarity)  // 使用最大值作为总相似度
                            });
                            break;  // 找到一个匹配就跳出内层循环
                        }
                    }
                } catch (err) {
                    console.error('匹配元素错误:', err);
                }
            }
            
            // 按总相似度排序
            results.sort((a, b) => b.totalSimilarity - a.totalSimilarity);
            return results;
        })();
        """ % (json.dumps(selectors_info), threshold)
        
        def handle_results(results):
            if not results:
                self.update_status("未找到新的匹配元素")
                return
                
            # 获取当前已有的文本集合（用于去重）
            existing_texts = {self.data_table.item(row, 0).text() 
                            for row in range(self.data_table.rowCount())}
            
            # 添加新的匹配结果（去重）
            new_count = 0
            for result in results:
                text = result['text']
                truncated_text = self.truncate_text(text)
                
                # 检查是否已存在（使用截断后的文本比较）
                if truncated_text not in existing_texts:
                    existing_texts.add(truncated_text)
                    row = self.data_table.rowCount()
                    self.data_table.insertRow(row)
                    # 在表格中显示截断的文本
                    self.data_table.setItem(row, 0, QTableWidgetItem(truncated_text))
                    # 设置完整文本作为工具提示
                    tooltip_text = (
                        f"文本: {text}\n"
                        f"选择器相似度: {result['selectorSimilarity']:.2%}\n"
                        f"类名相似度: {result['classSimilarity']:.2%}\n"
                        f"最大相似度: {result['totalSimilarity']:.2%}"
                    )
                    self.data_table.item(row, 0).setToolTip(tooltip_text)
                    self.selector.selected_elements.append(result)
                    new_count += 1
            
            if new_count > 0:
                self.update_status(f"找到 {new_count} 个新的匹配元素 (相似度阈值: {threshold:.0%})")
            else:
                self.update_status("未找到新的匹配元素")
        
        self.browser.page().runJavaScript(js, handle_results)
        
if __name__ == '__main__':
    # 确保images目录存在
    if not os.path.exists('images'):
        os.makedirs('images')
        
    app = QApplication(sys.argv)
    window = WebScraperApp()
    window.show()
    sys.exit(app.exec_())
