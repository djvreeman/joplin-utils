# joplin-utils
Collection of tools for working with [Joplin](https://joplinapp.org/), the open source note taking app. These python tools make use of the [Joplin Data API](https://joplinapp.org/api/references/rest_api/), which is available whenever the clipper server is running.



## Other Dependencies

These tools make use of other python modules you'll need:

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
- [Click](https://click.palletsprojects.com)
- Requests

Install them with pip:

```console
pip install click
pip install requests
pip install PyMuPDF
```

## file-uploader.py

> &#11088; This utility is based on the excellent "Hot Folder" implementation by [@JackGruber](https://github.com/JackGruber/Joplin-Tools)

This module enables uploading of a specified file as a note (with tags, etc) into Joplin via the API. It was designed to support integration into [Hazel](https://www.noodlesoft.com/) automation workflows.

Images and text (Mimetype `text/plain`) are inserted directly into the note, other Files are added as attachment. 

**Note:** The file is deleted after processing!

If you want to insert files directly as text, define them with the `--as-plain` switch.

### **Example**

```python
python3 file-uploader.py -n "Inbox" -p "/Users/djvreeman/joplin-import" -f "2022 08 30 - TSC Update Webinar.pdf" --tag "pdf,presentation,HL7"
```

### Parameters

- `-t` Joplin Authorization token. Default: `Ask for token and store token`
  - If no token is specified, the script will ask for it and then store it in the script's directory for later use when called without the `-t` option.

- `-u` Joplin Web Clipper URL. Default `http://localhost:41184`

- `-d` Specify the notebook in which to place newly created notes. Default: `@Inbox`
- `-p` Folder for monitoring
- `--as-plain` Specify file extensions comma separated for input as text. Example: `.md, .json`
- `--tag` Specify of comma separated Tags which should be added to the note. Example: `scan, todo`
- `--preview` Create a preview of the first site from an PDF file.
