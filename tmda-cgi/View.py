#!/usr/bin/env python
#
# Copyright (C) 2002 Gre7g Luterman <gre7g@wolfhome.com>
#
# This file is part of TMDA.
#
# TMDA is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  A copy of this license should
# be included in the file COPYING.
#
# TMDA is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with TMDA; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

"View e-mail page for tmda-cgi."

import cgi
import email
import email.Header
import os
import re

import CgiUtil
import MyCgiTb
import Template

from TMDA import Defaults
from TMDA import Errors
from TMDA import Pending
from TMDA import Util

# Pre-calc the regular expressions
ImageType1   = re.compile("\.(GIF|JPG)$", re.I)
ImageType2   = re.compile("^image/")
MovieType1   = re.compile("\.(MOV|AVI|SWF)$", re.I)
MovieType2   = re.compile("^(video/|application/x-shockwave)")
PythonType1  = re.compile("\.(PY|PYC|PYO)$", re.I)
SoundType1   = re.compile("\.(AU|SND|MP3|WAV)$", re.I)
SoundType2   = re.compile("^audio/")
TextType1    = re.compile("\.(TXT)$", re.I)
ZipType1     = re.compile("\.(TGZ|ZIP|BZ|BZ2)$", re.I)
ZipType2     = re.compile("^application/zip")

def AddIcon(Part):
  "Add an appropriate attachment."
  
  Filename = Part.get_filename("")
  Icon = "exe"
  if ImageType1.search(Filename): Icon = "image"
  elif MovieType1.search(Filename): Icon = "movie"
  elif PythonType1.search(Filename): Icon = "python"
  elif SoundType1.search(Filename): Icon = "sound"
  elif TextType1.search(Filename): Icon = "text"
  elif ZipType1.search(Filename): Icon = "zip"
  elif ImageType2.search(Part.get_type("text/plain")): Icon = "image"
  elif MovieType2.search(Part.get_type("text/plain")): Icon = "movie"
  elif SoundType2.search(Part.get_type("text/plain")): Icon = "sound"
  elif ZipType2.search(Part.get_type("text/plain")): Icon = "zip"
  Attachment["Icon"]     = Icon
  Attachment["Filename"] = Filename
  Attachment["Size"]     = CgiUtil.Size(MsgSize = len(Part.as_string()))
  Attachment.Add()

def Show():
  "Show an e-mail in HTML."

  global Allow, Remove, Attachment, Divider, PartTemplate, T

  # Deal with a particular message?
  if Form.has_key("msgid"):
    PVars["MsgID"] = Form["msgid"].value
    PVars.Save()

  # Check to make sure they're not trying to access anything other than email
  if not re.compile("^\d+\.\d+\.msg$").search(PVars["MsgID"]):
    CgiUtil.TermError("<tt>%s</tt> is not a valid message ID." % PVars["MsgID"],
      "Program error / corrupted link.", "retrieve pending e-mail", "",
      "Recheck link or contact TMDA programmers.")

  # Fetch the queue
  Queue = Pending.Queue(descending = 1, cache = 1)
  Queue.initQueue()
  Queue._loadCache()

  # Get e-mail template
  T = Template.Template("view.html")
  T["MsgID"]      = PVars["MsgID"]
  T["EmailClass"] = PVars[("ViewPending", "EmailClass")]

  # Locate messages in pending dir
  Msgs = Queue.listPendingIds()
  try:
    MsgIdx = Msgs.index(PVars["MsgID"])
  except ValueError: # Oops.  Perhaps they released the message?  Get the list!
    raise Errors.MessageError

  # Any subcommands?
  if Form.has_key("subcmd"):

    # first/prev/next/last subcommands
    if Form["subcmd"].value == "first":
      MsgIdx = 0
      PVars["Pager"] = 0
    elif Form["subcmd"].value == "prev":
      if MsgIdx > 0:
        MsgIdx -= 1
        PVars["Pager"] -= 1
    elif Form["subcmd"].value == "next":
      if MsgIdx < (len(Msgs) - 1):
        MsgIdx += 1
        PVars["Pager"] += 1
    elif Form["subcmd"].value == "last":
      MsgIdx = len(Msgs) - 1
      PVars["Pager"] = len(Msgs)

    # Toggle headers?
    elif Form["subcmd"].value == "headers":
      if PVars[("ViewPending", "Headers")] == "short":
        PVars[("ViewPending", "Headers")] = "all"
      else:
        PVars[("ViewPending", "Headers")] = "short"

    else:
      # Read in e-mail
      try:
        MsgObj = Pending.Message(PVars["MsgID"])

        if Form["subcmd"].value == "delete":
          MsgObj.delete()
        elif Form["subcmd"].value == "release":
          MsgObj.release()
          PVars["InProcess"][PVars["MsgID"]] = 1
        elif Form["subcmd"].value == "white":
          MsgObj.whitelist()
          MsgObj.release()
          PVars["InProcess"][PVars["MsgID"]] = 1
        elif Form["subcmd"].value == "black":
          MsgObj.blacklist()
          MsgObj.delete()
        elif Form["subcmd"].value == "spamcop":
          CgiUtil.ReportToSpamCop(MsgObj)
          MsgObj.delete()
        del Msgs[MsgIdx]
      except IOError: pass

      # So which message are we on now?
      if len(Msgs) == 0: # Oops! None left!
        PVars.Save()
        raise Errors.MessageError
      if MsgIdx >= len(Msgs):
        MsgIdx = len(Msgs) - 1
      PVars["MsgID"] = Msgs[MsgIdx]

    # Save session
    PVars.Save()

  # Get message ID
  PVars["MsgID"] = Msgs[MsgIdx]

  # Grey out the first & prev buttons?
  if MsgIdx == 0:
    T["FirstButt1"]
    T["FirstButt1"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c10.gif"
width="18" height="18" alt="First">"""
    T["PrevButt1"]
    T["PrevButt1"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c11.gif"
width="11" height="18" alt="Prev">"""
    T["FirstButt2"]
    T["FirstButt2"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c10.gif"
width="18" height="18" alt="First">"""
    T["PrevButt2"]
    T["PrevButt2"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c11.gif"
width="11" height="18" alt="Prev">"""

  # Grey out the next & last buttons?
  if MsgIdx == (len(Msgs) - 1):
    T["NextButt1"]
    T["NextButt1"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c12.gif"
width="11" height="18" alt="Next">"""
    T["LastButt1"]
    T["LastButt1"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c13.gif"
width="18" height="18" alt="Last">"""
    T["NextButt2"]
    T["NextButt2"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c12.gif"
width="11" height="18" alt="Next">"""
    T["LastButt2"]
    T["LastButt2"] = """<img src="%(ThemeDir)s/buttons/subnav_r1_c13.gif"
width="18" height="18" alt="Last">"""

  # Use Javascript confirmation?
  if PVars[("General", "UseJSConfirm")] == "Yes":
    T["DeleteURL"]    = "javascript:ConfirmDelete()"
    T["BlacklistURL"] = "javascript:ConfirmBlacklist()"
    T["SpamCopURL"]   = "javascript:ConfirmSpamCop()"
  else:
    T["DeleteURL"]    = "%s?cmd=view&subcmd=delete&SID=%s" % \
      (os.environ["SCRIPT_NAME"], PVars.SID)
    T["BlacklistURL"] = "%s?cmd=view&subcmd=black&SID=%s" % \
      (os.environ["SCRIPT_NAME"], PVars.SID)
    T["SpamCopURL"]   = "%s?cmd=view&subcmd=spamcop&SID=%s" % \
      (os.environ["SCRIPT_NAME"], PVars.SID)

  # Read in e-mail
  MsgObj = Pending.Message(PVars["MsgID"])
  Queue._addCache(PVars["MsgID"])
  Queue._saveCache()

  # Extract header row
  HeaderRow = T["HeaderRow"]
  if PVars[("ViewPending", "Headers")] == "all":
    # Remove header table
    T["ShortHeaders"]

    # Generate all headers
    Headers = ""
    for Line in CgiUtil.Escape(MsgObj.show()).split("\n"):
      if Line == "": break
      # Decode internationalized headers
      for decoded in email.Header.decode_header( Line ):
        Headers += decoded[0] + " "
        if decoded[1]:
          T["CharSet"] = email.Charset.Charset(decoded[1]).input_charset
      Headers += "\n"
    T["Headers"] = '<pre class="Headers">%s</pre>' % Headers
  else:
    # Remove all header block
    T["AllHeaders"]

    # Generate short headers
    for Header in Defaults.SUMMARY_HEADERS:
      T["Name"]  = Header.capitalize()
      value = ""
      # Decode internationalazed headers
      for decoded in email.Header.decode_header( MsgObj.msgobj[Header] ):
        value += decoded[0] + " "
        if decoded[1]:
          T["CharSet"] = email.Charset.Charset(decoded[1]).input_charset
      T["Value"] = CgiUtil.Escape(value)
      HeaderRow.Add()

  # Go through each part and generate HTML
  Allow        = re.split("[,\s]+", PVars[("ViewPending", "AllowTags")])
  Remove       = re.split("[,\s]+", PVars[("ViewPending", "BlockRemove")])
  Attachment   = T["Attachment"]
  Divider      = T["Divider"]
  PartTemplate = T["Part"]

  ShowPart(MsgObj.msgobj)

  # Remove unneeded bits?
  NumCols = int(T["NumCols"])
  if not Defaults.PENDING_BLACKLIST_APPEND:
    NumCols -= 1
    T["BlIcon1"]
    T["BlIcon2"]
  if not Defaults.PENDING_WHITELIST_APPEND:
    NumCols -= 1
    T["WhIcon1"]
    T["WhIcon2"]
  if not PVars[("General", "SpamCopAddr")]:
    NumCols -= 1
    T["SCIcon1"]
    T["SCIcon2"]
  T["NumCols"] = NumCols
  if len(Attachment.HTML) == 0:
    T["NoAttachments"]

  # Display HTML page with email included.
  print T

def ShowPart(Part):
  "Analyze message part and display it as best possible."

  # Each part is one of five things and must be handled accordingly
  # multipart/alternative - pick one and display it
  # message or multipart  - recurse through each
  # text/plain            - escape & display
  # text/html             - sterilize & display
  # other                 - show as an attachment


  # Display this part
  if Part.is_multipart():
    if Part.get_type("multipart/mixed") == "multipart/alternative":
      # Pick preferred alternative
      PrefPart   = None
      PrefRating = -1
      for SubPart in Part.get_payload():
        Type = SubPart.get_type("text/plain")
        Rating = PVars[("ViewPending", "AltPref")].find(Type)
        # Is this part preferred?
        if (not PrefPart) or ((PrefRating == -1) and (Rating >= 0)) \
          or ((Rating >= 0) and (Rating < PrefRating)):
          PrefPart   = SubPart
          PrefRating = Rating
      if PrefPart:
        ShowPart(PrefPart)
    else:
      # Recurse through all subparts
      for SubPart in Part.get_payload():
        ShowPart(SubPart)
  else:
    Type = Part.get_type("text/plain")
    # Display the easily display-able parts
    if Type == "text/plain":
      # Check if there's a character set for this part.
      if Part.get_content_charset():
        T["CharSet"] = \
          email.Charset.Charset(Part.get_content_charset()).input_charset
      # Escape & display
      try:
        Str = Part.get_payload(decode=1).strip()
        T["Content"] = CgiUtil.Escape(Str).replace("\n", "&nbsp;<br>")
        if len(PartTemplate.HTML) == 1:
          Divider.Add()
        PartTemplate.Add()
      except AttributeError:
        pass
    elif Type == "text/html":
      # Sterilize & display
      # Check if there's a character set for this part.
      if Part.get_content_charset():
        T["CharSet"] = \
          email.Charset.Charset(Part.get_content_charset()).input_charset
      try:
        T["Content"] = \
          CgiUtil.Sterilize(Part.get_payload(decode=1), Allow, Remove)
        if len(PartTemplate.HTML) == 1:
          Divider.Add()
        PartTemplate.Add()
      except AttributeError:
        pass
    else:
      # Display as an attachment
      AddIcon(Part)
