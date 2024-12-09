from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import os
import pyicloud
import requests
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
import pickle


generation_note = "Contact image imported from WhatsApp"
imgs_dir = "images"


@dataclass
class Contact:
    phone_number: str
    full_name: str

    @property
    def normalized_phone_number(self):
        return self.phone_number.replace(" ", "").replace("-", "")

    @property
    def abs_image_path(self):
        return os.path.abspath(self.rel_image_path)

    @property
    def rel_image_path(self):
        alpahbetic_name = "".join(e for e in self.full_name.lower() if e.isalpha())
        return os.path.join(imgs_dir, f"{alpahbetic_name}.jpg")

    def has_wa_image(self):
        return os.path.exists(self.rel_image_path)


class WhatsAppICloudSync:
    _wa_cookie_pickle = "wa_cookies.pkl"
    _icloud_cookie_pickle = "icloud_cookies.pkl"

    def __init__(self):
        self.driver = webdriver.Chrome()  # Or your preferred browser driver
        self.wait = WebDriverWait(self.driver, 30)
        self.contacts = []
        self.icloud = None
        self.is_first_search = True

    def _save_cookies(self, file_path):
        cookies = self.driver.get_cookies()
        with open(file_path, "wb") as file:
            pickle.dump(cookies, file)

    def _load_cookies(self, file_path):
        with open(file_path, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                self.driver.add_cookie(cookie)

    def login_whatsapp(self):
        self.driver.get("https://web.whatsapp.com")
        if os.path.exists(self._wa_cookie_pickle):
            self._load_cookies(self._wa_cookie_pickle)
        print("Please scan the QR code for WhatsApp Web")
        # Wait for WhatsApp to load (checking for presence of search box)
        self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            )
        )
        self._save_cookies(self._wa_cookie_pickle)
        print("WhatsApp Web logged in successfully")

    def login_icloud_api(self, apple_id, password):
        try:
            self.icloud = pyicloud.PyiCloudService(apple_id, password)
            if self.icloud.requires_2fa:
                print("Two-factor authentication required.")
                code = input("Enter the code you received: ")
                self.icloud.validate_2fa_code(code)
            print("iCloud logged in successfully")
        except Exception as e:
            print(f"iCloud login failed: {str(e)}")
            raise

    def login_icloud(self, apple_id, password):
        self.driver.get("https://www.icloud.com/")
        if os.path.exists(self._icloud_cookie_pickle):
            self._load_cookies(self._icloud_cookie_pickle)

        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@class="profile-avatar"]')
                )
            )
            time.sleep(1)
            # logged in
            return
        except:
            pass

        goto_signin_btn = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    # button with text Sign In
                    '//ui-button[contains(text(),"Sign In")]',
                )
            )
        )
        goto_signin_btn.click()

        sign_in_iframe = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//iframe[@id="aid-auth-widget-iFrame"]',
                )
            )
        )
        self.driver.switch_to.frame(sign_in_iframe)

        apple_id_input = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//input[@id="account_name_text_field"]',
                )
            )
        )
        apple_id_input.send_keys(apple_id)

        next_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//button[@id="sign-in"]',
                )
            )
        )
        next_btn.click()

        continue_with_pw_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//button[@id="continue-password"]',
                )
            )
        )
        continue_with_pw_btn.click()

        apple_pw_input = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//input[@id="password_text_field"]',
                )
            )
        )
        apple_pw_input.send_keys(password)

        signin_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//button[@id="sign-in"]',
                )
            )
        )
        signin_btn.click()

        self.driver.switch_to.default_content()
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[@class="profile-avatar"]'))
        )
        self._save_cookies(self._icloud_cookie_pickle)

    def _reset_wa_search(self):
        self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//button[@aria-label="Chat list" or @aria-label="Search or start new chat"]',
                )
            )
        ).click()

    def _download_whatsapp_profile_image(self, contact):
        try:
            search_box = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
                )
            )
            search_box.send_keys(contact.normalized_phone_number)

            self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//button[@aria-label="Cancel search"]')
                )
            )

            self.wait.until(
                EC.invisibility_of_element(
                    (
                        By.XPATH,
                        '//span[contains(text(),"Looking for chats, contacts or messages...")]',
                    )
                )
            )

            try:
                no_results = self.driver.find_element(
                    By.XPATH,
                    "//span[contains(text(),'No chats, contacts or messages found')]",
                )
                if no_results:
                    print(f"No results found for {contact.full_name}")
                    self._reset_wa_search()
                    return
            except:
                pass

            contact_tile = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        f'//div[@aria-label="Search results."]//span[@title="{contact.full_name}"]//ancestor::div[@role="button" or @role="listitem"]',
                    )
                )
            )
            contact_tile.click()
            time.sleep(0.5)

            contact_info = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//div[@title="Profile details"][@role="button"]')
                )
            )
            contact_info.click()
            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//h1[contains(text(),"Contact info")]',
                    )
                )
            )
            self.wait.until(
                EC.invisibility_of_element_located(
                    (
                        By.XPATH,
                        '//div[@aria-label="Loading photo"]',
                    )
                )
            )

            if self.is_first_search:
                time.sleep(3)
                self.is_first_search = False

            try:
                img_btn = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            '//section//div[@role="button"]/img/..',
                        )
                    )
                )
            except:
                print(f'"{contact.full_name}" does not have a profile image')
                self._reset_wa_search()
                return

            img_btn.click()

            img_element = self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//div[contains(@style, 'width') and contains(@style, 'height')]/div/img",
                    )
                )
            )
            img_url = img_element.get_attribute("src")

            response = requests.get(img_url)
            if response.status_code == 200:
                # save the image but change '.env' filename to '.jpg'
                with open(contact.rel_image_path, "wb") as file:
                    file.write(response.content)
                print(f'Profile image downloaded for "{contact.full_name}"')

            close_element = self.driver.find_element(
                By.XPATH,
                '//span[@data-icon="x-viewer"]',
            )
            close_element.click()
            self._reset_wa_search()
        except Exception as e:
            print(f"Error downloading profile image for {contact.full_name}: {str(e)}")
            self._reset_wa_search()

    def get_contacts(self):
        contacts = self.icloud.contacts.all()
        for contact in contacts:
            if "photo" in contact and (
                "notes" not in contact or generation_note not in contact["notes"]
            ):
                continue

            phone = None
            if "phones" in contact and len(contact["phones"]) > 0:
                if len(contact["phones"]) > 1:
                    for phone in contact["phones"]:
                        if "label" in phone and phone["label"] == "MOBILE":
                            phone = phone["field"]
                else:
                    phone = contact["phones"][0]["field"]
            name = contact["firstName"]
            if "lastName" in contact:
                name += " " + contact["lastName"]

            self.contacts.append(Contact(phone, name))

    def get_whatsapp_profile_images(self):
        for contact in self.contacts:
            self._download_whatsapp_profile_image(contact)

    def update_icloud_contacts(self):
        self.driver.get("https://www.icloud.com/contacts/")

        iframe = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[data-name='contacts']")
            )
        )

        self.driver.switch_to.frame(iframe)
        self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//a[@aria-label="Reload Contacts"]')
            )
        )

        for contact in self.contacts:
            if not contact.has_wa_image():
                continue
            try:
                self._update_icloud_contact(contact)
            except Exception as e:
                print(f"Error updating {contact.full_name}: {str(e)}")

    def _update_icloud_contact(self, contact):
        search_input = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//input[@aria-label='Search All Contacts']",
                )
            )
        )
        search_input.clear()

        search_input.send_keys(contact.phone_number)

        try:
            # check if no results found
            no_results = WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//span[contains(text(),"No results found")]',
                    )
                )
            )
            if no_results:
                raise ValueError(f"Contact {contact.full_name} not found")
        except TimeoutException:
            pass

        edit_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//label[contains(text(), "Edit")]/ancestor::div[@role="button"]',
                )
            )
        )
        edit_btn.click()

        add_photo_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//div[@tabindex="0"][contains(@class, "sc-view photo-icon sc-static-layout")]',
                )
            )
        )
        add_photo_btn.click()

        image_photo_file_input = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//input[@type='file'][@class='file-input']",
                )
            )
        )
        image_photo_file_input.send_keys(contact.abs_image_path)

        done_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//label[contains(text(),"Done")]/..',
                )
            )
        )
        done_btn.click()

        notes_textarea = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//textarea",
                )
            )
        )
        self.driver.execute_script("arguments[0].scrollIntoView();", notes_textarea)
        notes_value = notes_textarea.get_attribute("value")

        if generation_note in notes_value:
            new_notes = notes_value.replace(generation_note, generation_note)
        else:
            new_notes = notes_value + "\n\n" + generation_note
        notes_textarea.send_keys(new_notes)

        save_btn = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    '//label[contains(text(),"Save")]/ancestor::div[@role="button"]',
                )
            )
        )
        save_btn.click()

        self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//a[contains(@href,"tel:")]',
                )
            )
        )

    def cleanup(self):
        self.driver.quit()


def main():
    load_dotenv()
    apple_id = os.getenv("APPLE_ID")
    if apple_id is None:
        apple_id = input("Enter Apple ID: ")

    password = os.getenv("APPLE_PW")
    if password is None:
        password = input("Enter Password: ")

    syncer = WhatsAppICloudSync()
    try:
        syncer.login_icloud_api(apple_id, password)
        syncer.get_contacts()

        syncer.login_whatsapp()
        syncer.get_whatsapp_profile_images()

        syncer.login_icloud(apple_id, password)
        syncer.update_icloud_contacts()

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        syncer.cleanup()


if __name__ == "__main__":
    main()
