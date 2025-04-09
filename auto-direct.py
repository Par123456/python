from instagrapi import Client
import random
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor

class InstagramBot:
    def __init__(self):
        self.cl = Client()
        self.success_messages = [
            "✅ دایرکت خود را چک کنید",
            "🎉 پیام برای شما ارسال شد", 
            "👋 لطفا دایرکت خود را ببینید",
            "✨ پیام در دایرکت ارسال شد",
            "📩 پیام جدید در دایرکت",
            "🌟 دایرکت خود را بررسی کنید",
            "💫 پیام برایتان ارسال گردید",
            "📨 یک پیام جدید دارید"
        ]
        self.session_file = 'session.json'
        self.processed_users_file = 'processed_users.json'
        self.processed_users = self.load_processed_users()
        self.running = True
        self.dm_delay_range = (30, 90)
        self.comment_delay_range = (20, 60)

    def save_session(self):
        try:
            session_data = {
                'settings': self.cl.get_settings() 
            }
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f)
        except Exception as e:
            print(f"خطا در ذخیره سشن: {e}")

    def load_session(self):
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                    self.cl.set_settings(session_data['settings'])
                    self.cl.get_timeline_feed() 
                    return True
        except Exception as e:
            print(f"خطا در لود سشن: {e}")
            return False
        return False

    def save_processed_users(self):
        try:
            with open(self.processed_users_file, 'w') as f:
                json.dump(list(self.processed_users), f)
        except Exception as e:
            print(f"خطا در ذخیره کاربران پردازش‌شده: {e}")

    def load_processed_users(self):
        try:
            if os.path.exists(self.processed_users_file):
                with open(self.processed_users_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except:
            return set()

    def login(self):
        if self.load_session():
            print("سشن قبلی بازیابی شد!")
            return True

        try:
            username = input("نام کاربری را وارد کنید: ")
            password = input("رمز عبور را وارد کنید: ")

            self.cl.set_settings({
                "uuids": {k: self.cl.generate_uuid() for k in [
                    "phone_id", "uuid", "client_session_id", "advertising_id", "android_device_id"]},
                "cookie": {
                    "csrftoken": self.cl.generate_uuid(),
                    "ds_user_id": "0",
                    "mid": self.cl.generate_uuid(),
                    "rur": "0",
                    "sessionid": ""
                },
                "device_settings": {
                    "app_version": "203.0.0.29.118",
                    "android_version": "26",
                    "android_release": "8.0.0",
                    "dpi": "480dpi",
                    "resolution": "1080x1920",
                    "manufacturer": "OnePlus",
                    "device": "OnePlus5",
                    "model": "ONEPLUS A5000",
                    "cpu": "qcom",
                    "version_code": "314665256"
                },
                "user_agent": "Instagram 203.0.0.29.118 Android"
            })

            try:
                self.cl.login(username, password)
                print("با موفقیت وارد شدید!")
                self.save_session()
                return True
            except Exception as e:
                if "challenge_required" in str(e):
                    print("\nبرای ورود نیاز به تأیید هویت دارید")
                    verification_type = input("کد تأیید به کجا ارسال شود؟ (1: ایمیل، 2: پیامک): ")
                    choice = "1" if verification_type.strip() == "1" else "0"
                    self.cl.send_challenge_code(choice=choice)
                    print(f"کد تأیید به {'ایمیل' if choice == '1' else 'شماره موبایل'} شما ارسال شد")

                    while True:
                        code = input("کد تأیید را وارد کنید: ")
                        try:
                            self.cl.submit_challenge_code(code)
                            print("با موفقیت وارد شدید!")
                            self.save_session()
                            return True
                        except:
                            print("کد اشتباه بود، دوباره امتحان کنید.")
                else:
                    print(f"خطا در ورود: {str(e)}")
                    return False
        except Exception as e:
            print(f"خطا در ورود: {str(e)}")
            return False

    def get_media_info(self, url):
        try:
            if "stories" in url:
                story_pk = self.cl.story_pk_from_url(url)
                return self.cl.story_info(story_pk)
            else:
                media_pk = self.cl.media_pk_from_url(url)
                return self.cl.media_info(media_pk)
        except Exception as e:
            print(f"خطا در دریافت اطلاعات محتوا: {str(e)}")
            return None

    def process_media(self, media_info, target_comment, direct_message, media_type):
        if not media_info:
            print("محتوا نامعتبر است.")
            return

        if media_type != "story" and getattr(media_info, 'comments_disabled', False):
            print(f"کامنت‌ها برای این {media_type} غیرفعال است")
            return

        last_comment_time = None
        while self.running:
            try:
                comments = self.cl.media_comments(media_info.pk) if media_type != "story" else []
            except Exception as e:
                print(f"خطا در دریافت کامنت‌ها: {str(e)}")
                time.sleep(random.uniform(*self.comment_delay_range))
                continue

            for comment in comments:
                if comment.text == target_comment:
                    if last_comment_time and comment.created_at_utc <= last_comment_time:
                        continue
                    user_id = comment.user.pk
                    username = comment.user.username

                    if username == self.cl.username or user_id in self.processed_users:
                        continue

                    try:
                        
                        follows = self.cl.user_following(user_id)
                        if not follows:
                            print(f"کاربر {username} فالوور نیست - رد شد")
                            continue
                    except Exception as e:
                        print(f"خطا در بررسی وضعیت فالو {username}: {str(e)}")
                        continue

                    time.sleep(random.uniform(*self.dm_delay_range))
                    try:
                        thread = self.cl.direct_send(direct_message, [user_id])
                        if thread:
                            reply_text = random.choice(self.success_messages)
                            try:
                                self.cl.media_comment(media_info.pk, reply_text, replied_to_comment_id=comment.pk)
                            except Exception as e:
                                print(f"خطا در ارسال پاسخ کامنت: {str(e)}")
                            print(f"پیام به {username} در {media_type} ارسال شد")
                            self.processed_users.add(user_id)
                            self.save_processed_users()
                    except Exception as e:
                        print(f"خطا در ارسال پیام به {username}: {str(e)}")
                        if "direct messaging is disabled" in str(e):
                            print(f"کاربر {username} دایرکت را بسته است.")
            last_comment_time = max([c.created_at_utc for c in comments], default=last_comment_time)
            time.sleep(random.uniform(*self.comment_delay_range))

    def run(self):
        if not self.login():
            return

        media_list = []
        for i in range(8):
            print(f"\nتنظیمات محتوای شماره {i+1}:")
            print("1. پست\n2. ریلز\n3. استوری")
            media_type = input("نوع محتوا را انتخاب کنید: ").strip()
            if media_type not in ["1", "2", "3"]:
                print("ورودی نامعتبر، رد می‌شود")
                continue

            url = input("لینک محتوا را وارد کنید: ")
            target_comment = input("کامنت هدف را وارد کنید: ")
            direct_message = input("پیام دایرکت را وارد کنید: ")

            media_info = self.get_media_info(url)
            media_type_str = "post" if media_type == "1" else "reels" if media_type == "2" else "story"
            media_list.append((media_info, target_comment, direct_message, media_type_str))

        if not media_list:
            print("هیچ محتوای معتبری وارد نشد!")
            return

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self.process_media, *media) for media in media_list]
            try:
                input("\nبرای توقف برنامه کلید Enter را فشار دهید...\n")
                self.running = False
                for future in futures:
                    future.result()
            except KeyboardInterrupt:
                print("\nبرنامه متوقف شد")
            finally:
                self.running = False

    def cleanup(self):
        try:
            self.cl.logout()
            print("با موفقیت خارج شدید!")
        except Exception as e:
            print(f"خطا در خروج: {e}")

def main():
    if os.path.exists('instagrapi.json'):
        os.remove('instagrapi.json')
    bot = InstagramBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nبرنامه متوقف شد")
    finally:
        bot.cleanup()

if __name__ == "__main__":
    main()
