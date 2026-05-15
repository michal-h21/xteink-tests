#!/usr/bin/env lua

local lfs = require("lfs")

local input_dir = arg[1] or "images"
local output = arg[2] or "book.epub"
local tmp = "epub_tmp"

-- pomocná funkce
local function run(cmd)
  print(cmd)
  os.execute(cmd)
end

-- vytvoření struktury
run("rm -rf " .. tmp)
run("mkdir -p " .. tmp .. "/META-INF")
run("mkdir -p " .. tmp .. "/OEBPS/images")

-- mimetype (MUSÍ být bez komprese první v zipu)
local f = io.open(tmp .. "/mimetype", "w")
f:write("application/epub+zip")
f:close()

-- container.xml
local container = io.open(tmp .. "/META-INF/container.xml", "w")
container:write([[
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0"
 xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles>
   <rootfile full-path="OEBPS/content.opf"
    media-type="application/oebps-package+xml"/>
 </rootfiles>
</container>
]])
container:close()

-- načtení obrázků
local images = {}
for file in lfs.dir(input_dir) do
  if file:match("%.jpg$") or file:match("%.png$") or file:match("%.jpeg$") or file:match("%.bmp") then
    table.insert(images, file)
  end
end
table.sort(images)

-- kopírování obrázků
for _, img in ipairs(images) do
  run(string.format("cp '%s/%s' '%s/OEBPS/images/%s'", input_dir, img, tmp, img))
end

-- generování XHTML stránek
local manifest_items = {}
local spine_items = {}

for i, img in ipairs(images) do
  local page = string.format("page%d.xhtml", i)
  local id = string.format("img%d", i)

  local f = io.open(tmp .. "/OEBPS/" .. page, "w")
  f:write(string.format([[
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8"/>
<title>Image %s</title>
</head>
  <body>
    <div>
      <img src="images/%s" style="max-width:100%%;"/>
    </div>
  </body>
</html>
]], img, img))
  f:close()

  table.insert(manifest_items,
    string.format('<item id="%s" href="%s" media-type="application/xhtml+xml"/>', id, page))
  table.insert(manifest_items,
    string.format('<item id="imgfile%d" href="images/%s" media-type="image/%s"/>',
      i, img, img:match("%.([a-zA-Z]+)$")))
  table.insert(spine_items,
    string.format('<itemref idref="%s"/>', id))
end

math.randomseed(os.time())

local function uuid_v4()
  local template = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
  return string.gsub(template, "[xy]", function(c)
    local v = (c == "x") and math.random(0, 0xf)
                         or math.random(8, 0xb)
    return string.format("%x", v)
  end)
end
-- content.opf
local uuid = uuid_v4()

local opf = io.open(tmp .. "/OEBPS/content.opf", "w")
opf:write(string.format([[
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         version="3.0"
         unique-identifier="bookid">

  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:%s</dc:identifier>
    <dc:title>Image Book</dc:title>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">%s</meta>
  </metadata>

  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    %s
  </manifest>

  <spine>
    %s
  </spine>

</package>
]],
uuid,
os.date("!%Y-%m-%dT%H:%M:%SZ"),
table.concat(manifest_items, "\n"),
table.concat(spine_items, "\n")
))
opf:close()

local nav = io.open(tmp .. "/OEBPS/nav.xhtml", "w")

local nav_items = {}
for i = 1, #images do
  table.insert(nav_items,
    string.format('<li><a href="page%d.xhtml">Page %d</a></li>', i, i))
end

nav:write(string.format([[
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"  xmlns:epub="http://www.idpf.org/2007/ops">
  <head>
    <title>Table of Contents</title>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <ol>
        %s
      </ol>
    </nav>
  </body>
</html>
]], table.concat(nav_items, "\n")))

nav:close()

-- zabalení EPUB
run(string.format("cd %s && zip -X0 ../%s mimetype", tmp, output))
run(string.format("cd %s && zip -r ../%s META-INF OEBPS", tmp, output))

-- úklid
run("rm -rf " .. tmp)

print("Hotovo: " .. output)
