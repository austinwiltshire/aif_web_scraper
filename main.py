"""
A script to help find pictures for Iron Front

It's going to go through a list of RSS feeds, download any pictures, zip them and email them to an address.

Future features could include posting each picture to a discord channel then monitoring that channel for votes
on certain things like "contains gun," "contains cops," and "contains black block" 
"""
import shutil
import feedparser
from bs4 import BeautifulSoup
import posixpath
from urllib import request, parse
import tarfile
import logging
import os
import pytesseract
from sqlalchemy import Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class ImageUrl(Base):
    __tablename__ = "ImageUrl"
    image_url = Column(String, primary_key=True)


engine = create_engine("sqlite:///cache.db")
Base.metadata.create_all(engine)

Session = sessionmaker()
Session.configure(bind=engine)
session = Session()

logging.basicConfig(level=logging.DEBUG)

cached_image_urls = {result.image_url for result in session.query(ImageUrl).all()}

DOWNLOAD_DIRECTORY = "workspace"


def subreddit_to_images(feedname: str):
    """Takes a subreddit name and gets all the images in it's recent RSS feed, puts them in a working directory"""

    # TODO: assert format is in form of www.reddit.com/r/subreddit_name   no rss, or trailing /

    d = feedparser.parse(feedname + ".rss")

    for entry in d["entries"]:
        # download url into a folder
        assert (
            len(entry["content"]) == 1
        ), "Should only have one entry in content section"
        soup = BeautifulSoup(entry["content"][0]["value"], "html.parser")

        if not soup.img:
            continue

        assert soup.span, "We assume if there's an image there's a span"
        assert soup.span.a, "We assume if there's an image and span, there's a link"
        assert soup.span.a.attrs[
            "href"
        ], "We assume if there's an image, span and link, there's an href"

        img_url = soup.span.a.attrs["href"]
        full_img_name = parse.urlparse(img_url).path
        img_name = posixpath.split(full_img_name)[-1]
        img_type = posixpath.splitext(img_name)[-1]

        # Not an actual image. For instance, could be following to facebook.
        # TODO: put a breakpoint here and see if you can see patterns worth following
        if img_type not in [".jpg", ".png"]:
            logging.info(f"Didn't get image at {img_url}")
            continue

        if not os.path.exists(DOWNLOAD_DIRECTORY):
            os.mkdir(DOWNLOAD_DIRECTORY)

        if img_url in cached_image_urls:
            logging.info(f"{img_url} is a duplicate, skipping")
            continue

        # TODO: assert that the path has only one / in it, it's a simple path
        # the above is for reddit
        logging.info(f"Saved image to {DOWNLOAD_DIRECTORY} directory: {img_name}")
        request.urlretrieve(img_url, os.path.join(DOWNLOAD_DIRECTORY, img_name))

        session.add(ImageUrl(image_url=img_url))
        session.commit()


SUBREDDITS_OF_INTEREST = {"https://www.reddit.com/r/DallasProtests"}

for subreddit in SUBREDDITS_OF_INTEREST:
    subreddit_to_images(subreddit)

NO_WORDS_DIRECTORY = "no_words"
if not os.path.exists(NO_WORDS_DIRECTORY):
    os.mkdir(NO_WORDS_DIRECTORY)

# TODO: any initial analysis to rule out the easy ones

# TODO: we can look for test to rule out advertisements for protests.
# In my tests, protest signs were not picked up by OCR.
TESSERACT_FAIL_STR = " \n\x0c"
for filename in os.listdir(DOWNLOAD_DIRECTORY):
    current_full_path = os.path.join(DOWNLOAD_DIRECTORY, filename)
    if not os.path.isfile(current_full_path):
        continue

    text_in_image = pytesseract.image_to_string(current_full_path)
    if text_in_image != TESSERACT_FAIL_STR:
        logging.info(f"{filename} has words, assume this isn't a photo")
        continue

    logging.info(f"{filename} is being saved to be zipped")
    shutil.move(current_full_path, os.path.join(filename, NO_WORDS_DIRECTORY))

# I can see if it has an image tag in the content and use that as a check to download the actual image

# zip things up

tar = tarfile.open("images.tar.gz", "w:gz")
tar.add(NO_WORDS_DIRECTORY, arcname="Images")
tar.close()

# email the zip
if False:
    # Send email
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    port_number = 1234
    msg = MIMEMultipart()
    msg["From"] = "sender@protonmail.com"
    msg["To"] = "john.a.graham@gmail.com"
    msg["Subject"] = "My Test Mail "
    message = "This is the body of the mail"
    msg.attach(MIMEText(message))
    mailserver = smtplib.SMTP("localhost", port_number)
    mailserver.login("sender@protonmail.com", "mypassword")
    mailserver.sendmail(
        "sender@protonmail.com", "john.a.graham@gmail.com", msg.as_string()
    )
    mailserver.quit()

print("done")
