from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
import functools
import os
import time
from secrets import codice_fiscale, codice_ricetta

os.environ["TMPDIR"] = "/home/sof/snap/firefox/common/tmp"
os.environ["MOZ_HEADLESS"] = "1"

url_sardegna = "https://cupweb.sardegnasalute.it/web/guest/ricetta-elettronica?#!"


class InvalidStatus(Exception):
    pass


def get_status(driver):
    status = driver.find_elements(By.CLASS_NAME, "wizard-step")
    for el in status:
        if "active" in el.get_attribute("class"):
            return el.text
    raise InvalidStatus("FAIL")


def wait_helper(url, d):
    status = d.find_elements(By.CLASS_NAME, "wizard-step")
    return url != d.current_url and len(status) > 0


def wait_done(driver):
    WebDriverWait(driver, 100).until(functools.partial(wait_helper, driver.current_url))


def get_disponibilita(codice_fiscale, codice_ricetta):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.get(url_sardegna)
    try:

        cf_input = driver.find_element(
            By.ID,
            "_ricettaelettronica_WAR_cupprenotazione_:ePrescriptionSearchForm:CFInput",
        )
        nre_input = driver.find_element(
            By.ID,
            "_ricettaelettronica_WAR_cupprenotazione_:ePrescriptionSearchForm:nreInput0",
        )
        button = driver.find_element(
            By.NAME,
            "_ricettaelettronica_WAR_cupprenotazione_:ePrescriptionSearchForm:nreButton_button",
        )

        if get_status(driver) != "NRE":
            raise InvalidStatus(get_status(driver))

        cf_input.clear()
        cf_input.send_keys(codice_fiscale)
        nre_input.clear()
        nre_input.send_keys(codice_ricetta)
        button.click()
        wait_done(driver)

        if get_status(driver) != "Prestazioni":
            raise InvalidStatus(get_status(driver))

        button = driver.find_element(By.XPATH, "/html/body/div[1]/div[4]/p[2]/button")
        button.click()
        time.sleep(0.5)
        button = driver.find_element(
            By.NAME,
            "_ricettaelettronica_WAR_cupprenotazione_:navigation-prestazioni-under:prestazioni-nextButton-under__button",
        )
        button.click()
        wait_done(driver)

        if get_status(driver) != "Appuntamenti":
            raise InvalidStatus(get_status(driver))

        button = driver.find_element(
            By.XPATH, '//span[@aria-describedby="Altre disponibilità"]'
        )
        button.click()

        WebDriverWait(driver, 100).until(
            lambda d: len(d.find_elements(By.ID, "availableAppointmentsBlock")) > 0
        )

        res = []

        block = driver.find_element(By.ID, "availableAppointmentsBlock")
        els = block.find_elements(By.CLASS_NAME, "appuntamento")
        for el in els:
            cur = {}
            data = el.find_element(By.CLASS_NAME, "captionAppointment-when").text.split(
                "alle ore"
            )
            indirizzo = el.find_element(By.CLASS_NAME, "unita-address").text.split("-")
            note = el.find_elements(By.CLASS_NAME, "media")
            if len(note) > 0:
                cur["nota"] = note[0].get_attribute("textContent").strip()

            cur["data"] = data[0].strip()
            cur["ora"] = data[1].strip()
            cur["luogo"] = indirizzo[-1].strip()
            cur["raw"] = el.text.split("Seleziona")[0].strip()

            res.append(cur)
        return res
    finally:
        driver.close()


def main():
    print(get_disponibilita(codice_fiscale, codice_ricetta))


if __name__ == "__main__":
    main()
