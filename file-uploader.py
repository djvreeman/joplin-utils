#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

# Based on the "Hot Folder" implementation by @JackGruber
# https://github.com/JackGruber/Joplin-Tools
# 
# This module enables uploading of a specified file as a note (with tags, etc) into Joplin via the API

import click
import sys
import os
import time
from joplin import joplinapi

@click.command()
@click.option(
    "-n",
    "--notebook",
    "notebook",
    default="@Inbox",
    show_default=True,
    help="""Specify the notebook in which to place newly created notes."""
    """ Specified notebook must exist or program will exit.""",
)
@click.option(
    "-t",
    "--token",
    "token",
    required=False,
    help="""Specify the Joplin API token.""",
)
@click.option(
    "--tag",
    "add_tag",
    required=False,
    help="""Specify Tags to add to the note. Comma separated for multiple tags.""",
)
@click.option(
    "-p",
    "--path",
    "path",
    required=False,
    help="""Specify the folder for monitoring.""",
)
@click.option(
    "-f",
    "--file",
    "file",
    required=False,
    help="""Specify the file for uploading.""",
)
@click.option(
    "--as-plain",
    "plain",
    required=False,
    help="""Specify additional file extensions comma separated for input as text.""",
)
@click.option(
    "-u",
    "--url",
    "url",
    required=False,
    default="http://localhost:41184",
    show_default=True,
    help="""Specify the Joplin web clipper URL.""",
)
@click.option(
    "--preview/--no-preview",
    "preview",
    required=False,
    default=False,
    show_default=True,
    help="""Create a preview of the first site from an PDF file.""",
)
def Main(path, file, notebook, token, url, plain, add_tag, preview):
    if not os.path.exists(path):
        print("Path does not exist")

    if token is not None:
        joplinapi.SetEndpoint(url, token)
    elif joplinapi.LoadEndpoint() == False:
        joplinapi.SetEndpoint(url, token)

    while joplinapi.Ping() == False:
        print("Wait for Joplin")
        time.sleep(10)
    
    if plain is not None:
        plain = plain.replace(", ", ",")
        plain = plain.split(",")

    notebook_id = joplinapi.GetNotebookID(notebook)

    if notebook_id == False:
        print("Notebook not found")
        sys.exit(1)

    if add_tag is not None:
        add_tag = add_tag.replace(", ", ",")
        add_tag = add_tag.split(",")

    WatchFolder(path, file, notebook_id, plain, add_tag, preview)


def WatchFolder(path, file, notebook_id, plain, add_tags, preview):
    file_path = os.path.join(path, file)
    #if file.find(".lock") > 0:
    f = open(file_path + ".lock", 'w')
    f.close()

    print("Add to Joplin: " + file)
    note_id = joplinapi.CreateNoteWithFile(
        os.path.join(path, file), notebook_id, plain, preview)
    if note_id != False:
        if add_tags is not None:
            for tag in add_tags:
                joplinapi.AddTagToNote(tag, note_id, True)
        print("Joplin upload completed")
        try:
            os.remove(file_path)
            os.remove(file_path + ".lock")
        except:
            print("File remove failed: " + file)

if __name__ == "__main__":
    Main()
