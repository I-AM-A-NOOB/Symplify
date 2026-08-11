import sys
from typing import Optional, TYPE_CHECKING
import sympy as sp
from PySide6.QtCore import Qt, QPoint, QObject
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import (
    QOpenGLShaderProgram,
    QOpenGLShader,
)

if TYPE_CHECKING:
    from PySide6.QtOpenGL import QOpenGLFunctions


class SympyGLPlotter(QOpenGLWidget):
    # 类型注解：成员变量
    program: QOpenGLShaderProgram
    vao: int
    u_xMin: int
    u_xMax: int
    u_yMin: int
    u_yMax: int
    u_count: int
    u_color: int

    def __init__(self, expr, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.expr = expr  # SymPy 表达式，例如 sp.sin(x) / x

        # 视图范围（世界坐标）
        self.xMin, self.xMax = -6.0, 6.0
        self.yMin, self.yMax = -2.0, 2.0

        # 顶点数量（100k 个点，GPU 并行计算毫无压力）
        self.num_points = 100000

        # 鼠标交互记录
        self.last_mouse = QPoint()

        # 将 SymPy 表达式转为 GLSL 字符串
        # GLSLPrinter 自动处理 sin/cos/abs/分段函数(Piecewise -> 三元运算符)
        self.glsl_func = sp.printing.glsl.GLSLPrinter().doprint(self.expr)

        self.setMinimumSize(800, 600)

    def initializeGL(self):
        """初始化 OpenGL 着色器"""
        # 创建着色器程序
        self.program = QOpenGLShaderProgram()

        # ----- 顶点着色器 -----
        # 核心逻辑：gl_VertexID 是显卡给的索引，我们反推出 x，算出 y，再映射到 NDC(-1~1)
        # 替换原有的 vs_code 为以下防弹版本
        vs_code = f"""
#version 330 core
uniform float u_xMin;
uniform float u_xMax;
uniform float u_yMin;
uniform float u_yMax;
uniform int u_count;

float func(float x) {{
    return {self.glsl_func};
}}

void main() {{
    float t = float(gl_VertexID) / float(u_count);
    float x = u_xMin + (u_xMax - u_xMin) * t;
    float y = func(x);
    
    // ========== 防弹过滤层 ==========
    // 1. 检测无穷大、非数，或超出屏幕范围 1e8 倍的值
    if (isinf(y) || isnan(y) || abs(y) > 1e8) {{
        // 将位置设为 NaN，强制显卡丢弃该线段（断开连线）
        gl_Position = vec4(0.0 / 0.0);
        return;
    }}
    
    // 2. 安全钳制（防止残留的极大值把视图拉扯变形）
    y = clamp(y, -1e8, 1e8);
    // =================================

    // 世界坐标转 NDC（归一化设备坐标）
    float cx = (u_xMin + u_xMax) * 0.5;
    float cy = (u_yMin + u_yMax) * 0.5;
    float sx = (u_xMax - u_xMin) * 0.5;
    float sy = (u_yMax - u_yMin) * 0.5;
    
    // 防止视图范围缩到 0 导致除零闪退（限制最大缩放级别）
    sx = max(sx, 1e-12);
    sy = max(sy, 1e-12);
    
    float ndcX = (x - cx) / sx;
    float ndcY = (y - cy) / sy;
    
    gl_Position = vec4(ndcX, ndcY, 0.0, 1.0);
}}
"""

        vertex_shader = QOpenGLShader(QOpenGLShader.Vertex)
        vertex_shader.compileSourceCode(vs_code)
        if not vertex_shader.isCompiled():
            print("顶点着色器编译失败:", vertex_shader.log())
            return

        # ----- 片段着色器 (极简，纯色曲线) -----
        fs_code = """
        #version 330 core
        out vec4 FragColor;
        uniform vec3 u_color;
        void main() {
            FragColor = vec4(u_color, 1.0);
        }
        """
        fragment_shader = QOpenGLShader(QOpenGLShader.Fragment)
        fragment_shader.compileSourceCode(fs_code)
        if not fragment_shader.isCompiled():
            print("片段着色器编译失败:", fragment_shader.log())
            return

        # 链接程序
        self.program.addShader(vertex_shader)
        self.program.addShader(fragment_shader)
        self.program.link()
        if not self.program.isLinked():
            print("着色器链接失败:", self.program.log())
            return

        # 获取 uniform 句柄（缓存起来，避免每帧查找）
        self.u_xMin = self.program.uniformLocation("u_xMin")
        self.u_xMax = self.program.uniformLocation("u_xMax")
        self.u_yMin = self.program.uniformLocation("u_yMin")
        self.u_yMax = self.program.uniformLocation("u_yMax")
        self.u_count = self.program.uniformLocation("u_count")
        self.u_color = self.program.uniformLocation("u_color")

        # 现代 OpenGL 核心模式需要一个 VAO 才能绘制（哪怕它是空的）
        self.vao = self.context().functions().glGenVertexArrays()
        self.context().functions().glBindVertexArray(self.vao)

    def paintGL(self):
        """每帧刷新（拖动/缩放时高频触发）"""
        if not self.program or not self.program.isLinked():
            return

        funcs: QOpenGLFunctions = self.context().functions()
        funcs.glClearColor(0.08, 0.08, 0.12, 1.0)  # 深色科技风背景
        funcs.glClear(0x00004000)  # GL_COLOR_BUFFER_BIT

        self.program.bind()

        # 上传 4 个边界和点数到显存（仅 5 个 float/int，CPU 几乎零成本）
        # 使用 OpenGL 底层 API 避免类型转换问题
        funcs.glUniform1f(self.u_xMin, self.xMin)
        funcs.glUniform1f(self.u_xMax, self.xMax)
        funcs.glUniform1f(self.u_yMin, self.yMin)
        funcs.glUniform1f(self.u_yMax, self.yMax)
        funcs.glUniform1i(self.u_count, self.num_points)
        self.program.setUniformValue(self.u_color, 0.2, 0.8, 1.0)  # 亮蓝色

        # 绘制线带 (GL_LINE_STRIP = 0x0003)
        funcs.glDrawArrays(0x0003, 0, self.num_points)

        self.program.release()

    def resizeGL(self, w, h):
        """窗口大小变化时修正视口"""
        self.context().functions().glViewport(0, 0, w, h)

    # ------------------- 鼠标交互（丝滑拖动的关键） -------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self.last_mouse.x()
            dy = event.pos().y() - self.last_mouse.y()

            # 像素位移转世界坐标位移
            view_width = self.width()
            view_height = self.height()
            world_dx = (self.xMax - self.xMin) * dx / view_width
            world_dy = (self.yMax - self.yMin) * dy / view_height

            # 平移（注意鼠标向上拖动，y 增大，但屏幕坐标 y 向下，所以取反）
            self.xMin -= world_dx
            self.xMax -= world_dx
            self.yMin += world_dy  # 因为屏幕 y 轴向下，世界 y 轴向上
            self.yMax += world_dy

            self.last_mouse = event.pos()
            self.update()  # 触发 paintGL，但只上传 uniform，GPU 重算所有顶点

    def wheelEvent(self, event):
        """滚轮缩放（以鼠标位置为中心）"""
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # 缩放因子 (滚轮向上放大)
        factor = 0.9 if delta > 0 else 1.1

        # 计算鼠标在屏幕上的归一化位置 (0~1)
        mouse_x = event.position().x() / self.width()
        mouse_y = event.position().y() / self.height()

        # 鼠标位置对应的世界坐标
        center_x = self.xMin + (self.xMax - self.xMin) * mouse_x
        center_y = self.yMax - (self.yMax - self.yMin) * mouse_y  # 屏幕 y 翻转

        # 以鼠标位置为中心缩放
        half_w = (self.xMax - self.xMin) * factor / 2.0
        half_h = (self.yMax - self.yMin) * factor / 2.0

        self.xMin = center_x - half_w
        self.xMax = center_x + half_w
        self.yMin = center_y - half_h
        self.yMax = center_y + half_h

        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SymPy -> GLSL GPU 实时渲染")

        # ========== 在这里修改你的函数 ==========
        x = sp.Symbol("x")
        # 试试这些：
        expr = sp.sin(1 / x)  # 经典 sinc
        # expr = sp.exp(-x**2) * sp.sin(10*x)  # 衰减震荡
        # expr = sp.Piecewise((x, x < 0), (x**2, True))  # 分段函数测试
        # expr = sp.gamma(x)  # 伽马函数（如果 GLSL 不支持，会报错，慎用）
        # =====================================

        self.plotter = SympyGLPlotter(expr)
        self.setCentralWidget(self.plotter)
        self.resize(900, 600)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
