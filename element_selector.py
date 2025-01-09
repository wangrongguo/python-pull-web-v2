from PyQt5.QtCore import Qt, QEvent, QObject, pyqtSlot
from PyQt5.QtWidgets import QLabel, QTableWidgetItem
from PyQt5.QtWebEngineWidgets import QWebEngineView
from bs4 import BeautifulSoup
import json

class ElementSelector(QObject):
    def __init__(self, web_view: QWebEngineView, data_table, status_bar):
        super().__init__()
        self.web_view = web_view
        self.data_table = data_table
        self.status_bar = status_bar
        self.selector_mode = False
        self.highlight_label = None
        self.selected_elements = []
        self.seen_elements = set()  # 用于去重
        
        # 初始化高亮标签
        self.highlight_label = QLabel(web_view)
        self.highlight_label.setStyleSheet("background-color: rgba(255, 255, 0, 0.3);")
        self.highlight_label.hide()
        
        # 设置web_view的属性
        self.web_view.setMouseTracking(True)
        
        # 安装事件过滤器
        self.web_view.installEventFilter(self)
        print("ElementSelector initialized with event filter")
        
    def enable_selector_mode(self):
        print("启用选择模式")
        self.selector_mode = True
        self.status_bar.setText("选择模式已启用，点击网页元素进行选择")
        
        # 确保事件过滤器和鼠标跟踪都已启用
        self.web_view.setMouseTracking(True)
        self.web_view.installEventFilter(self)
        
        # 添加事件监听器
        js = """
        (function() {
            if (!window.qt || !window.qt.elementSelector) {
                console.error('QWebChannel未初始化，等待初始化完成...');
                return;
            }
            
            // 移除已存在的事件监听器
            document.removeEventListener('click', window._elementSelectorClickHandler, true);
            document.removeEventListener('mousemove', window._elementSelectorMouseHandler, true);
            
            // 定义点击事件处理函数
            window._elementSelectorClickHandler = function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                let element = e.target;
                if (!element) return;
                
                let info = {
                    text: (element.innerText || element.textContent || '').trim(),
                    html: element.outerHTML || '',
                    tagName: element.tagName || '',
                    className: element.className || '',
                    id: element.id || '',
                    href: element.href || '',
                    selector: window.getFullPath(element)
                };
                
                console.log('选中元素:', info);
                window.qt.elementSelector.handleElementClick(JSON.stringify(info));
            };
            
            // 定义鼠标移动事件处理函数
            window._elementSelectorMouseHandler = function(e) {
                let element = e.target;
                if (!element) return;
                
                // 移除之前的高亮
                let prevHighlight = document.querySelector('.element-selector-highlight');
                if (prevHighlight) {
                    prevHighlight.classList.remove('element-selector-highlight');
                }
                
                // 添加新的高亮
                element.classList.add('element-selector-highlight');
            };
            
            // 添加事件监听器
            document.addEventListener('click', window._elementSelectorClickHandler, true);
            document.addEventListener('mousemove', window._elementSelectorMouseHandler, true);
            
            console.log('元素选择器设置完成');
        })();
        """
        
        self.web_view.page().runJavaScript(js)
        print("事件监听器已安装")

    def disable_selector_mode(self):
        print("禁用选择模式")
        self.selector_mode = False
        self.status_bar.setText("选择模式已禁用")
        
        # 移除事件监听器
        js = """
        (function() {
            // 移除事件监听器
            document.removeEventListener('click', window._elementSelectorClickHandler, true);
            document.removeEventListener('mousemove', window._elementSelectorMouseHandler, true);
            
            // 移除高亮
            let prevHighlight = document.querySelector('.element-selector-highlight');
            if (prevHighlight) {
                prevHighlight.classList.remove('element-selector-highlight');
            }
            
            console.log('元素选择器已禁用');
        })();
        """
        self.web_view.page().runJavaScript(js)
        
        # 移除事件过滤器
        self.web_view.removeEventFilter(self)
        self.highlight_label.hide()

    def eventFilter(self, obj, event):
        if obj == self.web_view and self.selector_mode:
            if event.type() == QEvent.MouseMove:
                pos = event.pos()
                self.highlight_element_at(pos)
                return True
                
            elif event.type() == QEvent.MouseButtonPress:
                pos = event.pos()
                print(f"鼠标点击位置: {pos.x()}, {pos.y()}")
                js = """
                (function() {
                    try {
                        let element = document.elementFromPoint(%d, %d);
                        if (!element) return null;
                        
                        function getFullPath(el) {
                            try {
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
                            } catch (err) {
                                console.error('获取元素路径错误:', err);
                                return '';
                            }
                        }
                        
                        let info = {
                            text: (element.innerText || element.textContent || '').trim(),
                            html: element.outerHTML || '',
                            tagName: element.tagName || '',
                            className: element.className || '',
                            id: element.id || '',
                            href: element.href || '',
                            selector: getFullPath(element)
                        };
                        
                        return info;
                    } catch (err) {
                        console.error('获取元素信息错误:', err);
                        return null;
                    }
                })();
                """ % (pos.x(), pos.y())
                
                def handle_element_info(result):
                    if result:
                        try:
                            print("\n选中元素信息:")
                            print(f"标签: {result['tagName']}")
                            print(f"文本: {result['text']}")
                            print(f"选择器: {result['selector']}")
                            if result['id']:
                                print(f"ID: {result['id']}")
                            if result['className']:
                                print(f"类名: {result['className']}")
                            if result['href']:
                                print(f"链接: {result['href']}")
                            
                            # 将信息添加到表格
                            if result['text']:  # 只有当有文本内容时才添加
                                row = self.data_table.rowCount()
                                self.data_table.insertRow(row)
                                self.data_table.setItem(row, 0, QTableWidgetItem(result['selector']))
                                self.data_table.setItem(row, 1, QTableWidgetItem(result['text']))
                                self.selected_elements.append({
                                    'selector': result['selector'],
                                    'text': result['text'],
                                    'href': result.get('href', '')
                                })
                                self.status_bar.setText(f"已选择元素: {result['selector']}")
                        except Exception as e:
                            print(f"处理元素信息时出错: {str(e)}")
                            import traceback
                            traceback.print_exc()
                
                self.web_view.page().runJavaScript(js, handle_element_info)
                return True
                
        return super().eventFilter(obj, event)

    def highlight_element_at(self, pos):
        js = """
        (function() {
            try {
                let element = document.elementFromPoint(%d, %d);
                if (!element) return;
                
                // 移除之前的高亮
                let prevHighlight = document.querySelector('.element-selector-highlight');
                if (prevHighlight) {
                    prevHighlight.classList.remove('element-selector-highlight');
                }
                
                // 添加新的高亮
                element.classList.add('element-selector-highlight');
            } catch (err) {
                console.error('高亮元素错误:', err);
            }
        })();
        """ % (pos.x(), pos.y())
        
        self.web_view.page().runJavaScript(js)

    def add_element(self, selector, text, className='', href=''):
        """添加元素到表格，包含去重功能"""
        key = (selector, text)
        if key not in self.seen_elements:
            self.seen_elements.add(key)
            row = self.data_table.rowCount()
            self.data_table.insertRow(row)
            # 在表格中显示截断的文本
            truncated_text = text if len(text) <= 50 else text[:50] + "..."
            item = QTableWidgetItem(truncated_text)
            item.setToolTip(text)  # 设置完整文本作为工具提示
            self.data_table.setItem(row, 0, item)
            self.selected_elements.append({
                'selector': selector,
                'text': text,
                'className': className,
                'href': href
            })
            # 更新状态栏显示截断的文本
            status_text = f"已选择元素: {truncated_text}"
            self.status_bar.setText(status_text)
            return True
        return False

    @pyqtSlot(str)
    def handleElementClick(self, element_info_str):
        """处理从JavaScript传来的元素点击信息"""
        try:
            element_info = json.loads(element_info_str)
            if not self.selector_mode:  # 如果选择模式未启用，不处理点击事件
                return
                
            print("\n选中元素信息:")
            print(f"标签: {element_info['tagName']}")
            print(f"文本: {element_info['text']}")
            print(f"选择器: {element_info['selector']}")
            if element_info['id']:
                print(f"ID: {element_info['id']}")
            if element_info['className']:
                print(f"类名: {element_info['className']}")
            if element_info['href']:
                print(f"链接: {element_info['href']}")
            
            # 将信息添加到表格（带去重）
            if element_info['text']:  # 只有当有文本内容时才添加
                if self.add_element(
                    element_info['selector'],
                    element_info['text'],
                    element_info.get('className', ''),
                    element_info.get('href', '')
                ):
                    print("元素已添加到表格")
                else:
                    print("元素已存在，已跳过")
                    self.status_bar.setText("元素已存在，已跳过")
                    
        except Exception as e:
            print(f"处理元素信息时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def clear_data(self):
        """清空所有数据"""
        self.selected_elements.clear()
        self.seen_elements.clear()
        self.data_table.setRowCount(0)
