import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

def toggle_auto_reply():
    global auto_reply_status
    auto_reply_status = not auto_reply_status
    auto_reply_button.config(text="开启自动回复" if auto_reply_status else "关闭自动回复")
    # 这里可以调用实际的后端方法来开启或关闭自动回复

def open_config_page():
    def open_file():
        file_path = filedialog.askopenfilename(defaultextension=".txt",
                                               filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, "r") as file:
                    config_text.delete(1.0, tk.END)  # 清空当前内容
                    config_text.insert(tk.END, file.read())  # 插入文件内容
                config_window.title(f"用户配置 - {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件: {e}")

    def save_file():
        file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                 filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, "w") as file:
                    file.write(config_text.get(1.0, tk.END))
                messagebox.showinfo("信息", "配置已保存")
                config_window.title(f"用户配置 - {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件: {e}")

    config_window = tk.Toplevel(root)
    config_window.title("用户配置")

    # 文本编辑框
    config_text = scrolledtext.ScrolledText(config_window, wrap=tk.WORD, width=80, height=20)
    config_text.pack(padx=10, pady=10)

    # 打开和保存按钮
    open_button = tk.Button(config_window, text="打开配置文件", command=open_file)
    open_button.pack(side=tk.LEFT, padx=5, pady=5)

    save_button = tk.Button(config_window, text="保存配置文件", command=save_file)
    save_button.pack(side=tk.LEFT, padx=5, pady=5)

def update_transparency(value):
    root.attributes('-alpha', float(value))

# 创建主窗口
root = tk.Tk()
root.title("主界面")

auto_reply_status = False

# 自动回复按钮
auto_reply_button = tk.Button(root, text="开启自动回复", command=toggle_auto_reply)
auto_reply_button.pack(pady=10)

# 用户配置页面按钮
config_button = tk.Button(root, text="打开用户配置页面", command=open_config_page)
config_button.pack(pady=10)

# 透明度调整条
transparency_slider = tk.Scale(root, from_=0.1, to_=1.0, orient="horizontal", label="调整透明度", resolution=0.1, command=update_transparency)
transparency_slider.set(1.0)  # 设置初始透明度为不透明
transparency_slider.pack(pady=10)

# 启动主循环
root.mainloop()
