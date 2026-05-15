# Xteink tests

Testing of various methods of PDF file conversion for the Xteink X4 reader. 

## Source

The testing file is created using LuaLaTeX: 

```bash
$ lualatex sample.tex
```

## XTC conversion

You can convert PDF to XTC using the  `nosplit.py` script. It is based on [cbz2xtc](https://github.com/srokl/cbz2xtc/tree/main), the change is that it contains the `--no-split` option which prevents it from spliting pages to multiple images, like the original script does:

```bash
$ python nosplit.py --no-split --clean --no-dither --2bit sample.pdf
```

## XTC viewer

You can check quality of the XTC file using the [XTC Viewer](https://github.com/SimoGecko/XtcViewer/tree/main). It is just a self-containing HTML that can display XTC files.
