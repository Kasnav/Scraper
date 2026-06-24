import time

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import json
import threading

import hashlib
import re
from datetime import datetime
import redis

from Scraper.datasetManager import json_to_excel

from Scraper.semantic import semantic_filter

from Scraper.llm_filtration import evaluate_and_score_tenders

keywordList = []
keywordIndexes = ["Health", "Defence", "Corporate", "Pets"]

# with open('Health.json', 'r') as file:
import os

BASE_DIR = os.path.dirname(__file__)

with open(os.path.join(BASE_DIR, 'Health.json'), 'r') as file:
    HealthWords = json.load(file)
    keywordList.append(HealthWords)

# with open('Defence.json', 'r') as file:
with open(os.path.join(BASE_DIR, 'Defence.json'), 'r') as file:
    DefenceWords = json.load(file)
    keywordList.append(DefenceWords)

with open(os.path.join(BASE_DIR, 'Corporate.json'), 'r') as file:
    CorporateWords = json.load(file)
    keywordList.append(CorporateWords)

with open(os.path.join(BASE_DIR, 'Pets.json'), 'r') as file:
    PetsWords = json.load(file)
    keywordList.append(PetsWords)

adapters = [
    {
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-tenders?isExactMatch=true&order=DESC&pageNumber=1&pageSize=50&sortBy=startDate",
        "iframe": ["True", [[1, "iframe"]]],
        "refreshMode": "dom",
        "keywordSearchBox": [[1, "input"]],
        "submitButton": [[3, ".eui-button"]],
        "IdentifierForTenderList": "sedia-result-card-calls-for-tenders",
        "NextPageButton": [[3, ".eui-paginator__page-navigation-item"], [1, "button"]],
        "InitialTenderLinks": ".eui-u-text-link",
        "OrganizationName": "a.ng-star-inserted",
        "TenderTitle": ".eui-common-header__label-text",
        "BidOpeningDate": [[4, "eui-card-content"], [4, ".eui-label"]],
        "BidEndDate": [[4, "eui-card-content"], [6, ".eui-label"]],
        "WorkDescription": [[2, "eui-card"], [7, ".ng-star-inserted"]],
        "TenderValue": [[2, "eui-card"], [3, ".row"], [6, "div"]],
        "StatusIndicator": [[False, "Closed"], "sedia-project-status"],
        "ResultsIndicatorText": "No results found",
        "BackButton": [False],
        "Country": "European Union"
    },
    {
        "url": "https://www.gebiz.gov.sg/ptn/opportunity/BOListing.xhtml",
        "iframe": ["False"],
        "refreshMode": "navigation",
        "keywordSearchBox": [[2, "input.inputText_MAIN"]],
        "submitButton": '.subBannerSearchBar_BUTTON-GO',
        "IdentifierForTenderList": [[1, ".formRepeat_MAIN"], ".formColumns_MAIN"],
        "NextPageButton": [[1, 'input.formRepeatPagination2_NAVIGATION-BUTTON[value="Next"]']],
        "InitialTenderLinks": "a.commandLink_TITLE-BLUE",
        "OrganizationName": [[1, '[id="contentForm:j_idt252"]'], [1, ".formOutputText_VALUE-DIV"]],
        "TenderTitle": ".outputText_TITLE-BLACK",
        "BidOpeningDate": [[4, ".formOutputText_VALUE-DIV"]],
        "BidEndDate": [[7, ".formOutputText_HIDDEN-LABEL"]],
        "TimePeriod": [[9, "div.formOutputText_MAIN"], [1, "div.formOutputText_VALUE-DIV"]],
        "WorkDescription": [[1, "td.table_TABLE-CELL-TD"], [1, "span"]],
        "TenderValue": [[3, "td.table_TABLE-CELL-TD"], [1, "span"]],
        "StatusIndicator": [[False, "Closed"], '.outputText_LABEL-GRAY'],
        "ResultsIndicatorText": "No opportunity found for your search",
        "BackButton": [True, [[1, ".commandButton_BACK-BLUE"], [1, "input"]]],
        "Country": "Singapore"
    },
    {
        "url": "https://www.find-tender.service.gov.uk/Search/Results",
        "iframe": ["False"],
        "refreshMode": "dom",
        "keywordSearchBox": "input#keywords",
        "submitButton": "button#adv_search_button",
        "IdentifierForTenderList": [[1, "div.notice-search-results"], "div.search-result"],
        "NextPageButton": "a.standard-paginate-next",
        "InitialTenderLinks": "a.search-result-rwh",
        "OrganizationName": [[1, "div.govuk-grid-row ul.govuk-list"], [1, "li"]],
        "TenderTitle": "h1.govuk-heading-l",
        "BidOpeningDate": [[3, "div.govuk-grid-row"], [3, 'p[class*="govuk-body-s"]']],
        "TimePeriod": [[4, "ul.govuk-list"], [2, "li"]],
        "WorkDescription": [[3, ("div.govuk-body")]],
        "TenderValue": [[3, "ul.govuk-list"]],
        "BidEndDate": [[2, "div.content-block"], [1, "p.govuk-body"]],
        "StatusIndicator": [[True, "Submission deadline"], [[1, 'dl[aria-labelledby*="heading"]'], [".length - 2", ".search-result-entry"], [1, "dt"]]],
        "ResultsIndicatorText": "We've found 0 notices",
        "Country": "UK",
        "BackButton": [False]
    },
    {
        "url": "https://www.tenders.gov.au/atm",
        "iframe": ["False"],
        "keywordSearchBox": [[1, "input#form-Keyword"]],
        "submitButton": [[1, "button.searchIcon"]],
        "IdentifierForTenderList": [[1, "div.container div.boxEQH"], 'div.row'],
        "NextPageButton": [[1, 'a[rel="next"]']],
        "InitialTenderLinks": "a.detail",
        "TenderTitle": [[1, "div.box.boxY p.lead"]],
        "OrganizationName": [[2, "div.list-desc-inner"]],
        "BidEndDate": [[1, 'span:has(label[for="CloseDate"]) + div.list-desc-inner']],
        "BidOpeningDate": [[1, 'span:has(label[for="PublishDate"]) + div.list-desc-inner']],
        "WorkDescription": [[1, 'span:has(label[for="Description"]) + div.list-desc-inner'], [1, "p"]],
        "TimePeriod": [[1, 'span:has(label[for="TimeframeForDelivery"]) + div.list-desc-inner'], [1, "p"]],
        "TenderValue": "Nothing",
        #Closed tenders aren't shown:
        "StatusIndicator": [[True, "Close Date & Time:"], [[2, "div.list-desc"], [1, "span"]]],
        "ResultsIndicatorText": "There are no results that match your selection.",
        "BackButton": [False],
        "Country": "Australia"
    },
    {
        "url": "https://defproc.gov.in/nicgep/app?page=Home&service=page",
        "iframe": ["False"],
        "refreshMode": "dom",
        "keywordSearchBox": [[1, "input#SearchDescription"]],
        "submitButton": [[1, "input#Go"]],
        "IdentifierForTenderList": [[1, "table#table tbody"], "tr.even, tr.odd"],
        "NextPageButton": [[1, "a#linkFwd"]],
        "InitialTenderLinks": "td:nth-child(5) a",
        "TenderTitle": [[6, ".tablebg"], [1, "tbody"], [1, "tr"], [1, ".td_field"]],
        "OrganizationName": [[1, ".tablebg"], [1, "tbody"], [1, "tr"], [1, ".td_field"]],
        "BidEndDate": [[7, ".tablebg"], [1, "tbody"], [4, "tr"], [2, ".td_field"]],
        "BidOpeningDate": [[7, ".tablebg"], [1, "tbody"], [1, "tr"], [2, ".td_field"]],
        "WorkDescription": [[6, ".tablebg"], [1, "tbody"], [2, "tr"], [1, ".td_field"]],
        "TimePeriod": [[6, ".tablebg"], [1, "tbody"], [6, "tr"], [3, ".td_field"]],
        "TenderValue": [[6, ".tablebg"], [1, "tbody"], [5, "tr"], [1, ".td_field"]],
        "BackButton": [True, [[1, 'a[title="Back"]']]],
        "ResultsIndicatorText": "No Records Found",
        "Country": "India"
    }
]

gotNoResults = None

r = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)

def get_iframe_query_string(returnContentDocument, adapter):
    selectorStr = "document"
    if adapter["iframe"][0] == "True":
        if isinstance(adapter["iframe"][1], list):
            for level in adapter["iframe"][1]:
                if isinstance(level, list):
                    selectorStr += f"?.querySelectorAll('{level[1]}')[{int(level[0]) - 1}]"
                else:
                    selectorStr += f"?.querySelector('{level}')"
            if returnContentDocument:
                return f"{selectorStr}?.contentDocument"
            else:
                return selectorStr
        else:
            # selectorStr += f"?.querySelector('{adapter["iframe"]}')"
            selectorStr += f"?.querySelector('{adapter['iframe']}')"
            if returnContentDocument:
                return f"{selectorStr}?.contentDocument"
            else:
                return selectorStr
    return selectorStr


def getElementQueryString(elementKey, adapter):
    if adapter["iframe"][0] == "True":
        selectorStr = get_iframe_query_string(True, adapter)
    else:
        selectorStr = "document"
    if elementKey == "BackButton":
        if isinstance(adapter[elementKey][1], list):
            for level in adapter[elementKey][1]:
                if isinstance(level, list):
                    selectorStr += f"?.querySelectorAll('{level[1]}')[{int(level[0]) - 1}]"
                else:
                    selectorStr += f"?.querySelector('{level}')"
            return selectorStr
        else:
            selectorStr += f"?.querySelector('{adapter[elementKey]}')"
            return selectorStr

    if isinstance(adapter[elementKey], list):
        for level in adapter[elementKey]:
            if isinstance(level, list):
                selectorStr += f"?.querySelectorAll('{level[1]}')[{int(level[0]) - 1}]"
            else:
                selectorStr += f"?.querySelector('{level}')"
        return selectorStr
    else:
        selectorStr += f"?.querySelector('{adapter[elementKey]}')"
        return selectorStr


def get_element(page, elementKey, adapter, trueElement=False):
    handle = page.evaluate_handle(
        f"() => {getElementQueryString(elementKey, adapter)}"
    )
    element = handle.as_element()
    if element is None:
        if not trueElement:
            return get_element_inner_text(True, None)
        else:
            return

    if not trueElement:
        return get_element_inner_text(False, element)
    else:
        return element


def get_element_inner_text(failedToFindElement, element):
    if failedToFindElement:
        return "-"
    else:
        return element.inner_text()


def getElementQueryStringForListItems(adapter):
    if adapter["iframe"][0] == "True":
        selectorStr = get_iframe_query_string(True, adapter)
    else:
        selectorStr = "document"
    if isinstance(adapter["IdentifierForTenderList"], list):
        for level in adapter["IdentifierForTenderList"]:
            if isinstance(level, list):
                selectorStr += f"?.querySelectorAll('{level[1]}')[{int(level[0]) - 1}]"
            else:
                selectorStr += f"?.querySelectorAll('{level}')"
        return selectorStr
    else:
        # selectorStr += f"?.querySelectorAll('{adapter["IdentifierForTenderList"]}')"
        selectorStr += f"?.querySelectorAll('{adapter['IdentifierForTenderList']}')"
        return selectorStr


def get_leaf_selector(selector_value):
    if isinstance(selector_value, str):
        return f"?.querySelector('{selector_value}')"
    if isinstance(selector_value, list):
        selectorStr = ""
        for level in selector_value:
            if isinstance(level, list):
                if not isinstance(level[0], int):
                    selectorStr += f"?.querySelectorAll('{level[1]}')"
                    selectorStr += f"[listItem{selectorStr}{level[0]}]"
                else:
                    selectorStr += f"?.querySelectorAll('{level[1]}')[{int(level[0]) - 1}]"
            else:
                selectorStr += f"?.querySelectorAll('{level}')"
        return selectorStr
    return str(selector_value)


def install_custom_selector_loop(page, adapter):
    leaf_selector = get_leaf_selector(adapter["InitialTenderLinks"])
    try:
        status_leaf_selector = get_leaf_selector(adapter["StatusIndicator"][1])
    except KeyError:
        status_leaf_selector = ""

    script = f"""
            () => {{
                window.__assignTenderCustomSelectors = () => {{
                    let iterator = 0;
                    let parent = document;

                    if ("{adapter["iframe"][0]}" == "True") {{
                        parent = {get_iframe_query_string(True, adapter)};
                        if (!parent) return;
                    }}

                    const tenderCards = {getElementQueryStringForListItems(adapter)};

                    tenderCards?.forEach((listItem) => {{
                        listItem.classList.add(`custom-tenderList-${{iterator}}`);

                        // Scoped to listItem, not document
                        const InitialTenderLink = listItem{leaf_selector};
                        if (InitialTenderLink) {{
                           InitialTenderLink.classList.add(`custom-InitialTenderLinks-${{iterator}}-0`);
                        }}

                        // Scoped to listItem, not document — moved inside forEach
                        const statusIndicator = listItem{status_leaf_selector};
                        if (statusIndicator) {{
                            statusIndicator.classList.add("custom-statusIndicator");
                        }}

                        iterator += 1;
                    }});

                    const NextPageButton = {getElementQueryString("NextPageButton", adapter)};
                    if (NextPageButton) {{
                        NextPageButton.classList.add("custom-NextPageButton");
                    }}

                    const keywordSearchElement = {getElementQueryString("keywordSearchBox", adapter)};
                    if (keywordSearchElement) {{
                        keywordSearchElement.classList.add("custom-keywordSearchElement");
                    }}

                    const submitButtonElement = {getElementQueryString("submitButton", adapter)};
                    if (submitButtonElement) {{
                        submitButtonElement.classList.add("custom-submitButtonElement");
                    }}

                }};

                window.__assignTenderCustomSelectors();

                if (window.__customSelectorInterval) {{
                    clearInterval(window.__customSelectorInterval);
                }}

                window.__customSelectorInterval = setInterval(() => {{
                    window.__assignTenderCustomSelectors();
                }}, 250);
            }}
        """

    page.evaluate(script)


def wait_for_js_visible(page, js_selector, timeout=60000, poll_interval=0.25):
    start = time.time()

    while True:
        try:
            is_visible = page.evaluate(
                f"""
                () => {{
                    const element = {js_selector};

                    if (!element) return false;

                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();

                    return (
                        style.display !== "none" &&
                        style.visibility !== "hidden" &&
                        style.opacity !== "0" &&
                        rect.width > 0 &&
                        rect.height > 0
                    );
                }}
                """
            )
        except Exception as e:
            # Execution context destroyed mid-navigation — not fatal, just wait and retry
            if "Execution context was destroyed" in str(e) or "navigation" in str(e).lower():
                if (time.time() - start) * 1000 > timeout:
                    raise PlaywrightTimeoutError(
                        f"Timeout while waiting for JS element to become visible: {js_selector}"
                    )
                time.sleep(poll_interval)
                continue
            raise  # Re-raise anything unexpected

        if is_visible:
            return True

        if (time.time() - start) * 1000 > timeout:
            raise PlaywrightTimeoutError(
                f"Timeout while waiting for JS element to become visible: {js_selector}"
            )

        time.sleep(poll_interval)


def wait_for_url_change(page, old_url_two, timeout=30000):
    page.wait_for_function(
        """oldUrl => window.location.href !== oldUrl""",
        arg=old_url_two,
        timeout=timeout
    )


def get_all_tender_link(page):
    handle = page.evaluate_handle(
        f"() => document.querySelectorAll('.eui-u-text-link')[10]"
    )

    link_element = handle.as_element()

    if link_element is None:
        raise Exception(f"Could not find link")

    return link_element


def extract_currency_and_budget(value):
    text = str(value)
    currency = None
    # Fetch these values from online
    currency_map = {"EUR": 95, "USD": 83, "GBP": 111, "INR": 1}

    for curr in currency_map.keys():
        if curr in text.upper():
            currency = curr
            break

    numbers = re.findall(
        r'\d[\d,]*',
        text
    )

    cleaned = []
    for num in numbers:
        try:
            cleaned.append(int(num.replace(",", "")))
        except:
            pass

    budget_min = None
    budget_max = None

    if len(cleaned) >= 2:
        budget_min = cleaned[0]
        budget_max = cleaned[1]

    elif len(cleaned) == 1:
        budget_min = cleaned[0]
        budget_max = cleaned[0]

    inr_min = None
    inr_max = None

    if currency in currency_map:
        rate = currency_map[currency]
        if budget_min is not None:
            inr_min = budget_min * rate
        if budget_max is not None:
            inr_max = budget_max * rate

    return (
        currency,
        budget_min,
        budget_max,
        inr_min,
        inr_max
    )


def runMainLogic(page, parent, keyword, category, adapter, timer=1):
    install_custom_selector_loop(page, adapter)

    try:
        lists = parent.locator('[class*="custom-tenderList-"]')
        lists.first.wait_for(state="attached", timeout=60000)
    except:
        return

    tender_count = lists.count()

    for listNumber in range(tender_count):
        install_custom_selector_loop(page, adapter)

        card = lists.nth(listNumber)

        # Depending on whether a tender has ended, is ongoing, is closed, or is open for participation, the website structure is different.
        # Hence, we're only going through the structure for open tenders
        try:
            adapter["StatusIndicator"]
            try:
                status = card.locator(".custom-statusIndicator").inner_text(timeout=5000).strip()
                print(status)
            except PlaywrightTimeoutError:
                print("Timed out finding status label. Moving onto next list item")
                continue
        except KeyError:
            pass
        try:
            if not adapter["StatusIndicator"][0][0]:
                if not str(status) == str(adapter["StatusIndicator"][0][1]):
                    element = card.locator('[class*="custom-InitialTenderLinks-"]').first

                    old_url = page.evaluate("() => window.location.href")
                    before_signature = get_results_signature(page, adapter)
                    element.click()
                    wait_for_url_change(page, old_url)
                    wait_for_results_signature_change_or_stability(
                        page,
                        adapter,
                        before_signature=before_signature,
                    )
                    wait_for_js_visible(page, getElementQueryString("OrganizationName", adapter))

                    try:
                        organizationNameElement = get_element(page, "OrganizationName", adapter=adapter)
                        tenderTitle = get_element(page, "TenderTitle", adapter=adapter)
                        bidOpeningDate = get_element(page, "BidOpeningDate", adapter=adapter)
                        bidEndDate = get_element(page, "BidEndDate", adapter=adapter)
                        workDescription = get_element(page, "WorkDescription", adapter=adapter)
                        tenderValue = get_element(page, "TenderValue", adapter=adapter)
                    except:
                        print("Error while fetching information. Moving to next list item.")
                        continue

                    currency, budget_min, budget_max, inr_min, inr_max = extract_currency_and_budget(tenderValue)

                    primary_key = hashlib.md5(
                        (str(tenderTitle) + str(organizationNameElement)).encode()
                    ).hexdigest()

                    timeline = None
                    try:
                        open_date = datetime.strptime(
                            bidOpeningDate.strip(),
                            "%d/%m/%Y"
                        )
                        close_date = datetime.strptime(
                            bidEndDate.strip(),
                            "%d/%m/%Y"
                        )
                        timeline = (
                                close_date - open_date
                        ).days
                    except:
                        pass

                    tender_object = {
                        "Primary Key": primary_key,
                        "Country": adapter["Country"],
                        "Sector": category,
                        "Budget Currency": currency,
                        "Budget in Local Currency Minimum": budget_min,
                        "Budget in Local Currency Maximum": budget_max,
                        "Budget in INR Minimum": inr_min,
                        "Budget in INR Maximum": inr_max,
                        "Order Quantity": None,
                        "Expiry Date": bidEndDate,
                        "Opening Date": bidOpeningDate,
                        "Organisation Name": organizationNameElement,
                        "Link to the Tender": page.url,
                        "Tender Title": tenderTitle,
                        "Tender Description": workDescription,
                        "Special Observation": None,
                        "Award Date": None,
                        "Timeline": timeline,
                        "Eligibility": None,
                        "Keyword included": keyword,
                        "Application Status": "Not Applied",
                        "Current Applicants": None
                    }

                    redis_key = f"tender:{primary_key}"

                    cached_tender = r.get(redis_key)

                    if cached_tender:
                        cached_tender = json.loads(cached_tender)
                        keywords = cached_tender.get("Keywords", [])

                        if keyword not in keywords:
                            keywords.append(keyword)

                        cached_tender["Keywords"] = keywords

                        r.set(redis_key, json.dumps(cached_tender))
                        print(f"Updated existing tender -> {primary_key}")

                    else:
                        tender_object["Keywords"] = [keyword]
                        r.set(redis_key, json.dumps(tender_object))

                        print(json.dumps(tender_object, indent=4))
                        print("---------------------------------------")

                    before_signature = get_results_signature(page, adapter)

                    if adapter["BackButton"][0]:
                        get_element(page, "BackButton", adapter=adapter, trueElement=True).click()
                    else:
                        page.go_back(wait_until="domcontentloaded", timeout=60000)

                    wait_for_results_signature_change_or_stability(
                        page,
                        adapter,
                        before_signature=before_signature,
                    )

                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass

                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass

                    wait_for_js_visible(page, getElementQueryString("keywordSearchBox", adapter))
                    install_custom_selector_loop(page, adapter)
            else:
                if str(status) == str(adapter["StatusIndicator"][0][1]):
                    element = card.locator('[class*="custom-InitialTenderLinks-"]').first

                    old_url = page.evaluate("() => window.location.href")
                    before_signature = get_results_signature(page, adapter)
                    element.click()
                    wait_for_url_change(page, old_url)
                    wait_for_results_signature_change_or_stability(
                        page,
                        adapter,
                        before_signature=before_signature,
                    )
                    wait_for_js_visible(page, getElementQueryString("OrganizationName", adapter))

                    try:
                        organizationNameElement = get_element(page, "OrganizationName", adapter=adapter)
                        tenderTitle = get_element(page, "TenderTitle", adapter=adapter)
                        bidOpeningDate = get_element(page, "BidOpeningDate", adapter=adapter)
                        bidEndDate = get_element(page, "BidEndDate", adapter=adapter)
                        workDescription = get_element(page, "WorkDescription", adapter=adapter)
                        tenderValue = get_element(page, "TenderValue", adapter=adapter)
                    except:
                        print("Error while fetching information. Moving to next list item.")
                        continue

                    print(tenderTitle, status)
                    currency, budget_min, budget_max, inr_min, inr_max = extract_currency_and_budget(tenderValue)

                    primary_key = hashlib.md5(
                        (str(tenderTitle) + str(organizationNameElement)).encode()
                    ).hexdigest()

                    timeline = None
                    try:
                        open_date = datetime.strptime(
                            bidOpeningDate.strip(),
                            "%d/%m/%Y"
                        )
                        close_date = datetime.strptime(
                            bidEndDate.strip(),
                            "%d/%m/%Y"
                        )
                        timeline = (
                                close_date - open_date
                        ).days
                    except:
                        pass

                    tender_object = {
                        "Primary Key": primary_key,
                        "Country": adapter["Country"],
                        "Sector": category,
                        "Budget Currency": currency,
                        "Budget in Local Currency Minimum": budget_min,
                        "Budget in Local Currency Maximum": budget_max,
                        "Budget in INR Minimum": inr_min,
                        "Budget in INR Maximum": inr_max,
                        "Order Quantity": None,
                        "Expiry Date": bidEndDate,
                        "Opening Date": bidOpeningDate,
                        "Organisation Name": organizationNameElement,
                        "Link to the Tender": page.url,
                        "Tender Title": tenderTitle,
                        "Tender Description": workDescription,
                        "Special Observation": None,
                        "Award Date": None,
                        "Timeline": timeline,
                        "Eligibility": None,
                        "Keyword included": keyword,
                        "Application Status": "Not Applied",
                        "Current Applicants": None
                    }

                    redis_key = f"tender:{primary_key}"

                    cached_tender = r.get(redis_key)

                    if cached_tender:
                        cached_tender = json.loads(cached_tender)
                        keywords = cached_tender.get("Keywords", [])

                        if keyword not in keywords:
                            keywords.append(keyword)

                        cached_tender["Keywords"] = keywords

                        r.set(redis_key, json.dumps(cached_tender))
                        print(f"Updated existing tender -> {primary_key}")

                    else:
                        tender_object["Keywords"] = [keyword]
                        r.set(redis_key, json.dumps(tender_object))

                        print(json.dumps(tender_object, indent=4))
                        print("---------------------------------------")

                    before_signature = get_results_signature(page, adapter)

                    if adapter["BackButton"][0]:
                        get_element(page, "BackButton", adapter=adapter, trueElement=True).click()
                    else:
                        page.go_back(wait_until="domcontentloaded", timeout=60000)

                    wait_for_results_signature_change_or_stability(
                        page,
                        adapter,
                        before_signature=before_signature,
                    )

                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass

                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass

                    wait_for_js_visible(page, getElementQueryString("keywordSearchBox", adapter))
                    install_custom_selector_loop(page, adapter)
        except KeyError:
            element = card.locator('[class*="custom-InitialTenderLinks-"]').first

            old_url = page.evaluate("() => window.location.href")
            before_signature = get_results_signature(page, adapter)
            element.click()
            wait_for_url_change(page, old_url)
            wait_for_results_signature_change_or_stability(
                page,
                adapter,
                before_signature=before_signature,
            )
            wait_for_js_visible(page, getElementQueryString("OrganizationName", adapter))

            try:
                organizationNameElement = get_element(page, "OrganizationName", adapter=adapter)
                tenderTitle = get_element(page, "TenderTitle", adapter=adapter)
                bidOpeningDate = get_element(page, "BidOpeningDate", adapter=adapter)
                bidEndDate = get_element(page, "BidEndDate", adapter=adapter)
                workDescription = get_element(page, "WorkDescription", adapter=adapter)
                tenderValue = get_element(page, "TenderValue", adapter=adapter)
            except:
                print("Error while fetching information. Moving to next list item.")
                continue

            currency, budget_min, budget_max, inr_min, inr_max = extract_currency_and_budget(tenderValue)

            primary_key = hashlib.md5(
                (str(tenderTitle) + str(organizationNameElement)).encode()
            ).hexdigest()

            timeline = None
            try:
                open_date = datetime.strptime(
                    bidOpeningDate.strip(),
                    "%d/%m/%Y"
                )
                close_date = datetime.strptime(
                    bidEndDate.strip(),
                    "%d/%m/%Y"
                )
                timeline = (
                        close_date - open_date
                ).days
            except:
                pass

            tender_object = {
                "Primary Key": primary_key,
                "Country": adapter["Country"],
                "Sector": category,
                "Budget Currency": currency,
                "Budget in Local Currency Minimum": budget_min,
                "Budget in Local Currency Maximum": budget_max,
                "Budget in INR Minimum": inr_min,
                "Budget in INR Maximum": inr_max,
                "Order Quantity": None,
                "Expiry Date": bidEndDate,
                "Opening Date": bidOpeningDate,
                "Organisation Name": organizationNameElement,
                "Link to the Tender": page.url,
                "Tender Title": tenderTitle,
                "Tender Description": workDescription,
                "Special Observation": None,
                "Award Date": None,
                "Timeline": timeline,
                "Eligibility": None,
                "Keyword included": keyword,
                "Application Status": "Not Applied",
                "Current Applicants": None
            }

            redis_key = f"tender:{primary_key}"

            cached_tender = r.get(redis_key)

            if cached_tender:
                cached_tender = json.loads(cached_tender)
                keywords = cached_tender.get("Keywords", [])

                if keyword not in keywords:
                    keywords.append(keyword)

                cached_tender["Keywords"] = keywords

                r.set(redis_key, json.dumps(cached_tender))
                print(f"Updated existing tender -> {primary_key}")

            else:
                tender_object["Keywords"] = [keyword]
                r.set(redis_key, json.dumps(tender_object))

                print(json.dumps(tender_object, indent=4))
                print("---------------------------------------")

            before_signature = get_results_signature(page, adapter)

            if adapter["BackButton"][0]:
                get_element(page, "BackButton", adapter=adapter, trueElement=True).click()
            else:
                page.go_back(wait_until="domcontentloaded", timeout=60000)

            wait_for_results_signature_change_or_stability(
                page,
                adapter,
                before_signature=before_signature,
            )

            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            install_custom_selector_loop(page, adapter)

    before_signature = get_results_signature(page, adapter)
    try:
        nextPageButton = parent.locator(".custom-NextPageButton")
        nextPageButton.first.wait_for(state="attached")
        if nextPageButton.is_disabled():
            return
        else:
            old_first_card = parent.locator('[class*="custom-tenderList-"]').first
            old_first_card.wait_for(state="attached", timeout=3000)
            old_first_card_text = old_first_card.inner_text(timeout=3000)
            nextPageButton.click()
            wait_for_results_signature_change_or_stability(
                page,
                adapter,
                before_signature=before_signature,
            )
            wait_for_tender_results_refresh(page=page, old_first_card_text=old_first_card_text, adapter=adapter)
            runMainLogic(page, parent, keyword, category, adapter, timer=2)
    except:
        return


def wait_for_tender_results_refresh(page, adapter, old_first_card_text=None):
    try:
        return page.evaluate(
            f"""
            (args) => {{
                let doc = document;

                if ("{adapter["iframe"][0]}" == "True") {{
                    doc = {get_iframe_query_string(True, adapter)};
                    if (!doc || !doc.body) {{
                        return [false, false, "iframe document not ready"];
                    }}
                }}

                const bodyText = doc.body?.innerText || "";

                if (bodyText.includes(args.noResultsText)) {{
                    return [true, true, "no results found"];
                }}

                const firstCard = {getElementQueryStringForListItems(adapter)};

                if (!firstCard) {{
                    return [false, false, "no first card found after refresh"];
                }}

                return [true, false, "results loaded - same first card"];
            }}
            """,
            {
                "oldText": old_first_card_text,
                "noResultsText": adapter["ResultsIndicatorText"]
            }
        )
    except Exception as e:
        return [False, False, f"inspection failed: {str(e)}"]


def export_redis_to_json_and_clear(redis_client, json_filename="file.json"):
    all_tenders = []
    keys_to_delete = []

    for key in redis_client.scan_iter("tender:*"):
        key_type = redis_client.type(key)

        if key_type != "string":
            print(f"Skipping key '{key}' because it is type: {key_type}")
            continue

        value = redis_client.get(key)

        if value is None:
            continue

        try:
            tender = json.loads(value)
            all_tenders.append(tender)
            keys_to_delete.append(key)

        except json.JSONDecodeError:
            print(f"Skipping non-JSON Redis key: {key}")

    with open(json_filename, "w") as file:
        json.dump(all_tenders, file, indent=4)

    for key in keys_to_delete:
        redis_client.delete(key)

    print(f"Saved {len(all_tenders)} tenders to {json_filename}")
    print(f"Cleared {len(keys_to_delete)} Redis tender keys.")


def assign_custom_css_selector_on_iframe(page, adapter):
    script = f"""
            () => {{
                window.__assignTenderCustomSelectors = () => {{
                    {get_iframe_query_string(False, adapter)}?.classList?.add("custom-iframe")
                }};

                window.__assignTenderCustomSelectors();

                if (window.__customSelectorInterval) {{
                    clearInterval(window.__customSelectorInterval);
                }}

                window.__customSelectorInterval = setInterval(() => {{
                    window.__assignTenderCustomSelectors();
                }}, 100);
            }}
        """

    page.evaluate(script)


def wait_for_results_signature_change_or_stability(
        page,
        adapter,
        before_signature,
        timeout=60000,
        poll_interval=0.5,
        stable_for=1.5
):
    start = time.time()
    last_signature = None
    stable_since = None

    while True:
        current_signature = get_results_signature(page, adapter)

        if current_signature != before_signature:
            if current_signature == last_signature:
                if stable_since and time.time() - stable_since >= stable_for:
                    return current_signature
            else:
                last_signature = current_signature
                stable_since = time.time()

        if (time.time() - start) * 1000 > timeout:
            return current_signature

        time.sleep(poll_interval)


def get_results_signature(page, adapter):
    try:
        return page.evaluate(
            f"""
            () => {{
                let doc = document;

                if ("{adapter["iframe"][0]}" == "True") {{
                    doc = {get_iframe_query_string(True, adapter)};
                    if (!doc || !doc.body) return "NO_DOC";
                }}

                const bodyText = doc.body?.innerText || "";

                const noResultsPresent = bodyText.includes({json.dumps(adapter["ResultsIndicatorText"])});

                const firstCard = {getElementQueryStringForListItems(adapter)};
                const firstCardText = firstCard ? firstCard.innerText.trim() : "";

                return JSON.stringify({{
                    url: window.location.href,
                    noResultsPresent,
                    firstCardText,
                    bodyLength: bodyText.length
                }});
            }}
            """
        )
    except Exception as e:
        return f"ERROR:{str(e)}"


def click_and_wait_for_refresh(page, submit_button, adapter, timeout=60000):
    refresh_mode = adapter.get("refreshMode", "auto")

    if refresh_mode == "navigation":
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=timeout):
                submit_button.click()
        except Exception:
            try:
                submit_button.click()
            except Exception:
                pass

        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        return

    if refresh_mode == "dom":
        before_signature = get_results_signature(page, adapter)

        submit_button.click()

        wait_for_results_signature_change_or_stability(
            page,
            adapter,
            before_signature=before_signature,
            timeout=timeout
        )

        return

    # Auto fallback
    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=8000):
            submit_button.click()
    except Exception:
        try:
            submit_button.click()
        except Exception:
            pass

    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass


def scrape_site(adapter):
    with (Stealth().use_sync(sync_playwright()) as p):
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(adapter["url"], timeout=1200000)

        if adapter["iframe"][0] == "True":
            assign_custom_css_selector_on_iframe(page, adapter)
            parent = page.frame_locator(".custom-iframe")
            parent.locator("body *").first.wait_for(state="attached", timeout=60000)
        else:
            parent = page

        oldKeyword = ""
        for category in keywordList:
            for i in category["words"]:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except:
                    pass

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                install_custom_selector_loop(page, adapter)

                try:
                    keywordSearchBoxElement = parent.locator(".custom-keywordSearchElement")
                    keywordSearchBoxElement.first.wait_for(state="visible", timeout=60000)
                    keywordSearchBoxElement.fill(i)
                except PlaywrightTimeoutError:
                    page.go_back()
                    keywordSearchBoxElement = parent.locator(".custom-keywordSearchElement")
                    keywordSearchBoxElement.first.wait_for(state="visible", timeout=60000)
                    keywordSearchBoxElement.fill(i)

                try:
                    old_first_card = parent.locator('[class*="custom-tenderList-"]').first
                    old_first_card.wait_for(state="attached", timeout=3000)
                    old_first_card_text = old_first_card.inner_text(timeout=3000)
                except:
                    old_first_card_text = None

                submitButtonElement = parent.locator(".custom-submitButtonElement").first
                submitButtonElement.wait_for(state="visible", timeout=60000)

                click_and_wait_for_refresh(
                    page,
                    submitButtonElement,
                    adapter,
                    timeout=60000
                )

                install_custom_selector_loop(page, adapter)

                result_loaded, got_no_results, reason = wait_for_tender_results_refresh(
                    page,
                    adapter,
                    old_first_card_text=old_first_card_text
                )

                if got_no_results:
                    continue

                install_custom_selector_loop(page, adapter)
                runMainLogic(page, parent, keyword=i, category=keywordIndexes[keywordList.index(category)], adapter=adapter)


threads = []
for adapter in adapters:
    thread = threading.Thread(target=scrape_site, args=(adapter,))
    threads.append(thread)
    thread.start()

# for thread in threads:
#     thread.join()
for thread in threads:
    thread.join(timeout=180)

print("Finished waiting for scraper threads")
print("Collecting Redis tenders...")

all_tenders = []
for key in r.scan_iter("tender:*"):
    key_type = r.type(key)

    if key_type != "string":
        print(f"Skipping key '{key}' because it is type: {key_type}")
        continue

    value = r.get(key)

    if value is None:
        continue

    try:
        tender = json.loads(value)
        all_tenders.append(tender)
    except:
        print("Skipping non JSON Tender")


print("Running Layer 2: Semantic Embedding Filter...")
semantic_filter(all_tenders)

print("Running Layer 3: LLM Analytical Scorer Engine...")
evaluate_and_score_tenders(
    input_json_path="file.json", 
    output_json_path="file.json"
)
print("📊 Compiling Final Excel...")
json_to_excel(json_filename="file.json", excel_filename="live_tenders_pipeline.xlsx")
