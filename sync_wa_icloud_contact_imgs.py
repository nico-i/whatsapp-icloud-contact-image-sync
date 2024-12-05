from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import os
import base64
import pyicloud
import requests
from PIL import Image
from io import BytesIO


@dataclass
class Contact:
    phoneNumber: str
    imagePath: str = None


class WhatsAppICloudSync:
    def __init__(self):
        self.driver = webdriver.Chrome()  # Or your preferred browser driver
        self.wait = WebDriverWait(self.driver, 30)
        self.contacts = []
        self.icloud = None

    def login_whatsapp(self):
        self.driver.get("https://web.whatsapp.com")
        print("Please scan the QR code for WhatsApp Web")
        # Wait for WhatsApp to load (checking for presence of search box)
        self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            )
        )
        print("WhatsApp Web logged in successfully")

    def login_icloud(self, apple_id, password):
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

    def _reset_wa_search(self):
        search_element = self.driver.find_element(
            By.XPATH,
            '//span[@data-icon="search"]',
        )
        search_element.click()
        time.sleep(0.5)

    def _download_whatsapp_profile_image(self, phone, output_path):
        # Search for contact
        search_box = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
            )
        )
        search_box.clear()
        time.sleep(1)
        search_box.send_keys(phone)
        time.sleep(1)

        try:
            no_results = self.driver.find_element(
                By.XPATH,
                "//span[contains(text(),'No chats, contacts or messages found')]",
            )
            if no_results:
                print(f"No results found for {phone}")
                self._reset_wa_search()
                return
        except:
            pass

        # Click on the contact
        search_results = self.wait.until(
            EC.presence_of_all_elements_located(
                (
                    By.XPATH,
                    '//div[@class="_ak8h"]',
                )
            )
        )
        # select the element located the highest on the page
        contact = search_results[0]
        for result in search_results:
            if result.location["y"] < contact.location["y"]:
                contact = result

        contact.click()
        time.sleep(1)

        header = self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//header[@class="_amid"]'))
        )
        header.click()
        time.sleep(1)

        try:
            profile_img_btn = self.driver.find_element(
                By.XPATH,
                '//div[@role="button"][@class="x1n2onr6 x14yjl9h xudhj91 x18nykt9 xww2gxu" and @style="height: 200px; width: 200px; cursor: pointer;"]',
            )
        except:
            # business account
            profile_img_btn = self.driver.find_element(
                By.XPATH,
                '//div[@role="button"][@class="x1n2onr6 x14yjl9h xudhj91 x18nykt9 xww2gxu" and @style="height: 122px; width: 122px; cursor: pointer;"]',
            )
        profile_img_btn.click()
        time.sleep(0.5)

        try:
            no_photo_toast_element = self.driver.find_element(
                By.XPATH,
                '//span[contains(text(),"No profile photo")]',
            )
            if no_photo_toast_element:
                print(f"No profile photo found for {phone}")
                self._reset_wa_search()
                return
        except:
            pass

        img_element = self.driver.find_element(
            By.XPATH,
            '//img[@class="xhtitgo xh8yej3 x5yr21d _ao3e"]',
        )
        img_url = img_element.get_attribute("src")

        response = requests.get(img_url)
        if response.status_code == 200:
            # save the image but change '.env' filename to '.jpg'
            with open(output_path, "wb") as file:
                file.write(response.content)
            print(f"Profile image downloaded for {phone}")

        close_element = self.driver.find_element(
            By.XPATH,
            '//span[@data-icon="x-viewer"]',
        )
        close_element.click()

        self._reset_wa_search()

    def get_contacts(self):
        contacts = self.icloud.contacts.all()
        for contact in contacts:
            if "photo" in contact:
                if (
                    "notes" not in contact
                    or "Contact image imported from WhatsApp" not in contact["notes"]
                ):
                    continue
            if "phones" in contact and len(contact["phones"]) > 0:
                if len(contact["phones"]) > 1:
                    for phone in contact["phones"]:
                        if "label" in phone and phone["label"] == "MOBILE":
                            self.contacts.append(Contact(phone["field"]))
                else:
                    self.contacts.append(Contact(contact["phones"][0]["field"]))

    def get_whatsapp_profile_images(self):
        for contact in self.contacts:
            output_dir = "./images"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = f"{output_dir}/{contact.phoneNumber}.jpg"
            try:
                self._download_whatsapp_profile_image(contact.phoneNumber, output_path)
                contact.imagePath = output_path
            except Exception as e:
                print(f"Error processing {contact.phoneNumber}: {str(e)}")

    def update_icloud_contacts(self):
        contacts = self.icloud.contacts.all()
        current_time = datetime.now().isoformat()

        for contact in contacts:
            phone_numbers = []
            # Extract phone numbers from contact
            if hasattr(contact, "phones"):
                for phone in contact.phones:
                    # Format phone number to match WhatsApp format
                    formatted_phone = self.format_phone_number(phone.number)
                    phone_numbers.append(formatted_phone)

            for phone in phone_numbers:
                if phone in self.whatsapp_images:
                    should_update = False

                    # Check if contact has no image
                    if not hasattr(contact, "image") or not contact.image:
                        should_update = True

                    # Check for existing WhatsApp import note
                    if (
                        hasattr(contact, "note")
                        and "Profile imported from WhatsApp" in contact.note
                    ):
                        should_update = True
                    if should_update:
                        try:
                            # Convert base64 image to proper format
                            img_data = self.whatsapp_images[phone].split(",")[1]
                            img_binary = base64.b64decode(img_data)
                            image = Image.open(BytesIO(img_binary))

                            # Save image to temporary file
                            temp_path = f"temp_profile_{phone}.jpg"
                            image.save(temp_path, "JPEG")

                            # Update contact image
                            with open(temp_path, "rb") as image_file:
                                contact.image = image_file.read()

                            # Update or add note
                            note = f"Profile imported from WhatsApp on {current_time}"
                            if hasattr(contact, "note"):
                                contact.note = note
                            else:
                                contact.add_note(note)

                            # Save contact changes
                            contact.save()

                            # Clean up temporary file
                            os.remove(temp_path)

                            print(f"Updated contact: {contact.full_name}")
                        except Exception as e:
                            print(
                                f"Error updating contact {contact.full_name}: {str(e)}"
                            )

    def cleanup(self):
        self.driver.quit()


def main():
    syncer = WhatsAppICloudSync()
    try:
        # Login to both services
        syncer.login_whatsapp()
        syncer.login_icloud(input("Enter Apple ID: "), input("Enter Password: "))

        syncer.get_contacts()

        syncer.get_whatsapp_profile_images()

        # Update iCloud contacts
        syncer.update_icloud_contacts()

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        syncer.cleanup()


if __name__ == "__main__":
    main()
