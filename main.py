#!/usr/bin/env python
# pylint: disable=W1201, C0412

import json
import os
import sys
import pause
import logging.config
import random
import time
from selenium import webdriver
from dateutil import parser as date_parser
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC


logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [PID %(process)d] [Thread %(thread)d] [%(levelname)s] [%(name)s] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "default",
            "filename": "purchase.log"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
})

NIKE_HOME_URL = "https://www.nike.com/login"
NIKE_CART_URL = "https://www.nike.com/au/en/cart"
LOGGER = logging.getLogger()

def run(driver, username, password, login_time, release_time, url, shoe_sizes, cvv, auto_confirm_purchase,
        num_retries, page_load_timeout, screenshot_path="purchase.png", html_path="purchase.html"):
    try:
        driver.set_page_load_timeout(page_load_timeout)
        driver.maximize_window()
    except Exception as e:
        LOGGER.exception("Error in driver setup: " + str(e))

    if login_time:
        LOGGER.info("Waiting until login time: " + login_time)
        pause.until(date_parser.parse(login_time))

    for _ in range(num_retries):
        try:
            login(driver, username, password, page_load_timeout)
            break
        except Exception as e:
            LOGGER.exception("Failed to login: " + str(e))
    else:
        raise Exception("Failed to login.")

    if release_time:
        LOGGER.info("Waiting until release time: " + release_time)
        pause.until(date_parser.parse(release_time))

    LOGGER.info("Requesting page: " + url)
    driver.get(url)
    for shoe_size in shoe_sizes:
        for _ in range(num_retries):
            try:
                add_to_cart(driver, num_retries, shoe_size, page_load_timeout)
                break
            except Exception as e:
                LOGGER.exception("Failed to select shoe size and add to cart: " + str(e))
                LOGGER.info("Requesting page again: " + url)
                driver.get(url)
            else:
                raise Exception("Failed to select shoe size and add to cart.")

    try:
        checkout_cart(driver, cvv, auto_confirm_purchase, page_load_timeout)
    except Exception as e:
        LOGGER.exception("Failed to checkout cart: " + str(e))
        raise e

    if screenshot_path:
        LOGGER.info("Saving screenshot")
        driver.save_screenshot(screenshot_path)

    if html_path:
        LOGGER.info("Saving HTML source")
        with open(html_path, "w") as f:
            f.write(driver.page_source)


def random_type(element, word, base_delay_ms, range_delay_ms):
    element.clear()
    for c in word:
        element.send_keys(c)
        delay_ms = base_delay_ms + random.randrange(0, range_delay_ms)
        time.sleep(delay_ms / 1000)


def login(driver, username, password, page_load_timeout):
    human_reaction_sleep = 3
    try:
        LOGGER.info("Requesting page: " + NIKE_HOME_URL)
        driver.get(NIKE_HOME_URL)
    except TimeoutException:
        LOGGER.info("Page load timed out but continuing anyway")

    LOGGER.info("Waiting for login fields to become visible")
    wait_until_visible(driver, page_load_timeout, xpath="//input[@name='emailAddress']")
    time.sleep(human_reaction_sleep)

    LOGGER.info("Entering username and password")
    email_input = driver.find_element_by_xpath("//input[@name='emailAddress']")
    random_type(email_input, username, 100, 50)

    password_input = driver.find_element_by_xpath("//input[@name='password']")
    random_type(password_input, password, 100, 50)

    LOGGER.info("Logging in")
    driver.find_element_by_xpath("//input[@value='SIGN IN']").click()

    while True:
        try:
            dismiss_button = "//input[@value='Dismiss this error']"
            wait_until_visible(driver, page_load_timeout, xpath=dismiss_button)
            time.sleep(human_reaction_sleep)
            driver.find_element_by_xpath(dismiss_button).click()
            time.sleep(human_reaction_sleep)
            password_input = driver.find_element_by_xpath("//input[@name='password']")
            random_type(password_input, password, 100, 50)
            driver.find_element_by_xpath("//input[@value='SIGN IN']").click()
        except TimeoutException:
            LOGGER.info("No error message upon login")
            break

    wait_until_visible(driver, page_load_timeout, xpath="//div[@class='pre-avatar']")
    LOGGER.info("Successfully logged in")


def add_to_cart(driver, num_retries, shoe_size, page_load_timeout):
    page_transition_sleep = 1.5
    LOGGER.info("Waiting for size buttons to appear")
    wait_and_click(
        driver, num_retries, page_load_timeout,
        xpath="//*[not(name()='script') and translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='{}']".format(shoe_size.lower())
    )
    time.sleep(page_transition_sleep)

    LOGGER.info("Waiting for add to bag button to become clickable")
    wait_and_click(
        driver, num_retries, page_load_timeout,
        xpath="//*[not(name()='script') and contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'add to bag')]"
    )
    time.sleep(page_transition_sleep)

    # try:
    LOGGER.info("Waiting for added to bag confirmation")
    wait_and_click(driver, num_retries, page_load_timeout, xpath="//button[@aria-label='Close']")
    time.sleep(page_transition_sleep)
    # except Exception as e:
    #     LOGGER.warning("Confirmation failed: " + str(e))


def checkout_cart(driver, cvv, auto_confirm_purchase, page_load_timeout):
    try:
        LOGGER.info("Requesting page: " + NIKE_CART_URL)
        driver.get(NIKE_CART_URL)
    except TimeoutException:
        LOGGER.info("Page load timed out but continuing anyway")

    wait_and_click(driver, num_retries, page_load_timeout, xpath="//button[@data-automation='member-checkout-button']")

    try:
        wait_until_visible(driver, page_load_timeout, xpath="//div[@class='loading-spiner-holder']")
    except Exception as e:
        LOGGER.warning("Loading spinner was not visible: " + str(e))
    wait_until_invisible(driver, page_load_timeout, xpath="//div[@class='loading-spiner-holder']")
    wait_and_click(driver, num_retries, page_load_timeout, xpath="//span[@class='checkbox-checkmark']")
    wait_and_click(driver, num_retries, page_load_timeout, xpath="//button[@id='shippingSubmit']")
    wait_and_click(driver, num_retries, page_load_timeout, xpath="//button[@id='billingSubmit']")

    LOGGER.info("Entering CVV")
    driver.switch_to_default_content()
    wait_and_switch_iframe(driver, page_load_timeout, xpath="//iframe[@id='paymentIFrameEvo']")
    wait_and_switch_iframe(driver, page_load_timeout, xpath="//iframe[@id='stored-cards-iframe']")
    xpath = "//input[@name='cardCvv']"
    wait_until_visible(driver, page_load_timeout, xpath=xpath)
    cvv_input = driver.find_element_by_xpath(xpath)
    random_type(cvv_input, cvv, 150, 100)
    driver.switch_to.parent_frame()
    if auto_confirm_purchase:
        wait_and_click(driver, num_retries, page_load_timeout, xpath="//button[@id='stored-cards-paynow']")


def wait_until_clickable(driver, duration, xpath=None, class_name=None, frequency=0.1):
    if xpath:
        WebDriverWait(driver, duration, frequency).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    elif class_name:
        WebDriverWait(driver, duration, frequency).until(EC.element_to_be_clickable((By.CLASS_NAME, class_name)))


def wait_until_visible(driver, duration, xpath=None, class_name=None, frequency=0.1):
    if xpath:
        WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.XPATH, xpath)))
    elif class_name:
        WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.CLASS_NAME, class_name)))


def wait_until_invisible(driver, duration, xpath=None, class_name=None, frequency=0.1):
    if xpath:
        WebDriverWait(driver, duration, frequency).until(EC.invisibility_of_element_located((By.XPATH, xpath)))
    elif class_name:
        WebDriverWait(driver, duration, frequency).until(EC.invisibility_of_element_located((By.CLASS_NAME, class_name)))


def wait_and_click(driver, num_retries, duration, xpath, frequency=0.1):
    wait_until_clickable(driver, duration, xpath=xpath, frequency=frequency)
    for _ in range(num_retries):
        try:
            wait_until_clickable(driver, 1, xpath=xpath, frequency=frequency)
            driver.find_element_by_xpath(xpath).click()
            break
        except Exception as e:
            LOGGER.warning("Warning in clicking: " + str(e))
    else:
        raise Exception("Failure in clicking.")


def wait_and_switch_iframe(driver, duration, xpath=None, class_name=None, frequency=0.1):
    if xpath:
        WebDriverWait(driver, duration, frequency).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, xpath)))
    elif class_name:
        WebDriverWait(driver, duration, frequency).until(EC.frame_to_be_available_and_switch_to_it((By.CLASS_NAME, class_name)))


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    LOGGER.info("Loading config file: " + config_path)
    with open(config_path) as f:
        config = json.load(f)

    driver_type = config['driver_type']
    webdriver_path = config.get('webdriver_path', None)
    username = config['username']
    password = config['password']
    login_time = config.get('login_time', None)
    release_time = config.get('release_time', None)
    url = config['url']
    shoe_sizes = config['shoe_sizes']
    cvv = config['cvv']
    auto_confirm_purchase = config.get('auto_confirm_purchase', False)
    num_retries = config.get('num_retries', 10)
    page_load_timeout = config.get('page_load_timeout', 15)

    if webdriver_path is not None:
        executable_path = webdriver_path
    elif sys.platform == "darwin":
        executable_path = "./bin/chromedriver_mac"
    elif "linux" in sys.platform:
        executable_path = "./bin/chromedriver_linux"
    elif "win32" in sys.platform:
        executable_path = "./bin/chromedriver_win32.exe"
    else:
        raise Exception("Drivers for installed operating system not found.")

    if driver_type == "firefox":
        driver = webdriver.Firefox(executable_path=executable_path, log_path=os.devnull)
    elif driver_type == "chrome":
        driver = webdriver.Chrome(executable_path=executable_path)
    else:
        raise Exception("Specified web browser not supported, only Firefox and Chrome are supported at this point")

    try:
        run(driver, username, password, login_time, release_time, url, shoe_sizes, cvv, auto_confirm_purchase, num_retries, page_load_timeout)
    except Exception as e:
        LOGGER.exception("Failed run: " + str(e))
        print("Enter exit() to exit.")
        import pdb; pdb.set_trace()
        driver.quit()
