from playwright.sync_api import Playwright, sync_playwright, TimeoutError
import time
from customtkinter import *
from tkinter import Menu
import threading
from configparser import ConfigParser
import os
from plyer import notification


## Creating or Reading the configure file
config = ConfigParser()
# If configure file does not exit create it
if not os.path.exists('./config.ini'):
    config['DEFAULT'] = {
        'username': '',
        'password': '',
        'money_per_question': ''
    }
    with open("config.ini", "w") as f:
        config.write(f)


class App:
    def __init__(self, master):
        self.main = master
        self.main.title('Chegg Bot')
        self.state = 'LoggingIn'
        self.questions_this_month = 0
        self.money_this_month = 0
        global config

        # Reading the configure file
        config.read('./config.ini')
        self.username = StringVar(value=config['DEFAULT']['username'])
        self.password = StringVar(value=config['DEFAULT']['password'])
        self.money_per_question = DoubleVar(value=float(config['DEFAULT']['money_per_question']))

        # Menu bar
        menu_bar = Menu(self.main)
        setting_menu = Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="Options", menu=setting_menu)
        setting_menu.add_command(label='Settings', command=self.create_setting_window)
        setting_menu.add_separator()
        setting_menu.add_command(label="Exit", command=lambda: [self.main.destroy()])
        self.main.configure(menu=menu_bar)

        # Status text line
        self.status = CTkLabel(master=self.main, text='Press Start to start looking for question')
        self.status.pack(side = 'top', pady=10, fill='both')

        # Account Stats
        self.stats = CTkFrame(master=self.main)
        self.stats.pack(side='top', padx=10, pady=10, fill='both')
        self.QTM = CTkLabel(master=self.stats, text=f'Solved: {self.questions_this_month}')
        self.QTM.grid(row=0, column= 0, padx=(170, 10), pady=10)
        self.MTM = CTkLabel(master=self.stats, text=f'Earned: {self.money_this_month}')
        self.MTM.grid(row=0, column= 1, padx=10, pady=10)
        
        # Buttons
        self.button_frame = CTkFrame(master=self.main)
        self.button_frame.pack(side='top', padx=10, pady=10, fill='both')
        self.start_button = CTkButton(master=self.button_frame, text='Start', command=self.start_app, width=100)
        self.start_button.grid(row=1, column=0, padx=(70, 10), pady=10)
        self.pause_button = CTkButton(master=self.button_frame, text='Pause', command=self.pause_app, state='disabled', width=100)
        self.pause_button.grid(row=1, column=1, padx=10, pady=10)
        self.stop_button = CTkButton(master=self.button_frame, text='Close', command=self.stop_app, width=100)
        self.stop_button.grid(row=1, column=2, padx=10, pady=10)

        #!! Stay on Top Checkbutton
        # def checkbox_event():
        #     print("checkbox toggled, current value:", check_var.get())

        # check_var = customtkinter.StringVar(value="on")
        # checkbox = customtkinter.CTkCheckBox(self.main, text="CTkCheckBox", command=checkbox_event,
        #                                     variable=check_var, onvalue="on", offvalue="off")

        # Check if the password entered or not
        self.check_credentials()

        self.main.geometry('500x200')
        self.main.resizable(False, False)
        self.main.mainloop()

    def check_credentials(self):
        if self.username.get() == '' or self.password.get() == '':
            self.create_setting_window()
        
    def start_app(self):
        self.thread = threading.Thread(target=self.start_process, daemon=True)
        self.thread.start()

    def start_process(self):
        self.start_button.configure(state='disabled')
        self.pause_button.configure(state='normal')

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        context = self.browser.new_context()
        self.page = context.new_page()
        
        while True:
            if self.state == 'LoggingIn':
                self.status.configure(text='Logging In')

                self.page.goto("https://expert.chegg.com/auth/login?redirectTo=https%3A%2F%2Fexpert.chegg.com%2Fqna%2Fauthoring")
                self.page.locator("[data-test=\"login-email-input\"]").click()
                self.page.locator("[data-test=\"login-email-input\"]").fill(self.username.get())
                self.page.locator("[data-test=\"login-email-submit\"]").click()
                # Check for the username
                try:
                    if self.page.inner_text("""//*[@id="login-email-error-banner-message"]""", timeout=5000):
                        self.status.configure(text='Wrong Username. Fill a valid username and try again.', text_color='red')
                        self.state = 'Paused'
                        self.start_button.configure(state='disabled')
                        self.pause_button.configure(state='disabled')
                        continue
                except TimeoutError:
                    pass
                # Fill the password
                self.page.locator("[data-test=\"login-cred-pwd-input\"]").click()
                self.page.locator("[data-test=\"login-cred-pwd-input\"]").fill(self.password.get())
                self.page.locator("[data-test=\"login-cred-submit\"]").click()
                # Check for the password
                try:
                    if self.page.inner_text("""//*[@id="login-banner-message"]""", timeout=5000):
                        self.status.configure(text='Wrong Password. Fill a valid username and try again.', text_color='red')
                        self.state = 'Paused'
                        self.start_button.configure(state='disabled')
                        self.pause_button.configure(state='disabled')
                        continue
                except TimeoutError:
                    pass

                self.state = 'CheckForQuestion'

            elif self.state == 'CheckForQuestion':
                self.status.configure(text='Checking for Questions')
                self.pause_button.configure(state='normal')

                # Update the solved and earned labels
                self.CheckSolvedQuestions()

                # Checking for question
                self.page.locator("""[data-test-id=\"expert-qna-nav-link\"]""").click()

                # Wait until the page is loaded completely
                self.page.wait_for_load_state("networkidle")

                # Checking if there is 'Start Solving' button available using XPath
                if self.page.locator("""//*[@id="__next"]/main/div/div/footer/div/div[1]/div[2]/button/span/span[1]""").count() == 1:
                    self.state = 'ReviewQuestion'
                else:
                    self.status.configure(text='No Question found. The page will be refreshed in 10 seconds.')
                    time.sleep(10)
                    self.page.reload()

            elif self.state == 'ReviewQuestion':
                self.state = 'Paused'
                self.pause_app()
                self.status.configure(text='Review Question')

                # Notification
                notification.notify(title="Chegg Bot", message="Review Question", app_name="Chegg Bot")
                # , app_icon='./images/logo.ico')

            elif self.state == 'Paused':
                time.sleep(10)

    def pause_app(self):
        self.state = 'Paused'
        self.status.configure(text='Application is paused')
        self.pause_button.configure(state='disabled')
        self.start_button.configure(state='normal', command=self.resume_process)

    def resume_process(self):
        self.state = 'CheckForQuestion'

    def stop_app(self):
        self.main.destroy()

    def create_setting_window(self):
        try:
            # Disable the main
            self.main.attributes('-disabled', True)

            self.setting_window = CTkToplevel(self.main)
            self.setting_window.title('Settings')
            # # Icon of the main window
            # self.setting_window.iconbitmap('./icons/setting.ico')

            self.top_frame = CTkFrame(self.setting_window)
            self.bottom_frame = CTkFrame(self.setting_window)

            CTkLabel(master=self.top_frame, text='Username').grid(row=0, column=0, padx=10, pady=4, sticky=E)
            CTkEntry(master=self.top_frame,
                    textvariable=self.username,
                    width=250,
                    height=30,
                    justify='right'
                    ).grid(row=0, column=1, padx=10, pady=10)

            CTkLabel(master=self.top_frame, text='Chegg Password').grid(row=1, column=0, padx=10, pady=(0, 10), sticky=E)
            CTkEntry(master=self.top_frame,
                    textvariable=self.password,
                    width=250,
                    height=30,
                    show='*',
                    justify='right'
                    ).grid(row=1, column=1, padx=10, pady=(0, 10))

            CTkLabel(master=self.top_frame, text='Per Question Payment').grid(row=2, column=0, padx=10, pady=(0, 10), sticky=E)
            CTkEntry(master=self.top_frame,
                    textvariable=self.money_per_question,
                    width=250,
                    height=30,
                    justify='right'
                    ).grid(row=2, column=1, padx=10, pady=(0, 10))

            # Buttons
            CTkButton(master=self.bottom_frame,
                      text='Save',
                      width=100,
                      command=self.save_configuration).pack(side=LEFT, padx=(110,4), pady=10)
            CTkButton(master=self.bottom_frame,
                      text='Cancel',
                      width=100,
                      command=self.setting_window.destroy).pack(side=LEFT, padx=4, pady=10)

            self.top_frame.pack(side=TOP, padx=10, pady=10)
            self.bottom_frame.pack(side=TOP, padx=10, pady=(0, 10), fill=BOTH)

            # Configure setting_window
            self.setting_window.resizable(False, False)
            self.setting_window.grab_set()

            # Adds flicker effect
            self.setting_window.transient(self.main)
            # Wait for add_member_window to close
            self.main.wait_window(self.setting_window)
        finally:
            # Enable the main
            self.main.attributes('-disabled', False)
            # So that main stays on the top of other windows after closing the add_member_window
            self.main.lift()

    def save_configuration(self):
        config.set('DEFAULT', 'username', self.username.get())
        config.set('DEFAULT', 'password', self.password.get())
        config.set('DEFAULT', 'money_per_question', str(self.money_per_question.get()))
        with open('./config.ini', 'w') as f:
            config.write(f)
        
        # Close the setting window after saving the settings
        self.setting_window.destroy()
        self.state = 'LoggingIn'
        self.status.configure(text='Trying to Login', text_color='white')
    
    def CheckSolvedQuestions(self):
        # Click on the home page
        self.page.locator("""[data-test-id=\"qna-authoring-nav-link\"]""").click()
        self.page.locator("[data-test=\"select-stats-dropdown\"]").click()
        self.page.get_by_role("option", name="This month").click()
        try:
            div_content = self.page.locator("[data-test-id=\"answered\"]").text_content()
            self.questions_this_month = int(div_content.split(':')[1])
            self.money_this_month = self.money_per_question.get() * self.questions_this_month
        except Exception:
            return

        # Updates the labels
        self.QTM.configure(text=f'Solved: {self.questions_this_month}')
        self.MTM.configure(text=f'Earned: {self.money_this_month}')
        

if __name__ == '__main__':
    App(CTk())
