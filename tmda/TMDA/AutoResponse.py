# -*- python -*-
#
# Copyright (C) 2001,2002 Jason R. Mastaler <jason@mastaler.com>
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

"""Manage a TMDA-style Auto Response."""


from email import message_from_string
from email.Charset import add_alias
from email.Header import Header, decode_header
from email.MIMEMessage import MIMEMessage
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formataddr, parseaddr

import os
import time

import Defaults
import Util
import Version


DEFAULT_CHARSET = 'US-ASCII'

# Extend Charset.ALIASES with some charsets which don't already have
# convenient aliases.
add_alias('arabic', 'iso-8859-6')
add_alias('cyrillic', 'iso-8859-5')
add_alias('greek', 'iso-8859-7')
add_alias('hebrew', 'iso-8859-8')
add_alias('japanese', 'euc-jp')
add_alias('korean', 'euc-kr')
add_alias('russian', 'koi8-r')
add_alias('thai', 'tis-620')
add_alias('turkish', 'iso-8859-9')
add_alias('vietnamese', 'viscii')


class AutoResponse:
    def __init__(self, msgin, bouncetext, response_type, recipient):
        """
        msgin is an email.Message object representing the incoming
        message we are responding to.

        bouncetext is a string of rfc822 headers/body created from a
        TMDA template.

        response_type is the type of auto response we should send
        ('request' is a confirmation request, 'accept' is a
        confirmation acceptance notice, and 'bounce' is a failure
        notice).

        recipient is the recipient e-mail address of this auto
        response.  Normally the envelope sender address.
        """
        self.msgin = msgin
        self.msgin_as_string = self.msgin.as_string()
        self.msgin_size = len(self.msgin_as_string)
        self.bouncemsg = message_from_string(bouncetext)
        self.responsetype = response_type
        self.recipient = recipient
        self.bodycharset = self.bouncemsg.get('bodycharset')
        if self.bodycharset is None:
            self.bodycharset = DEFAULT_CHARSET


    def create(self):
        """
        Create an auto response object from whole cloth.

        The auto response is a MIME compliant entity with either one
        or two bodyparts, depending on what
        Defaults.AUTORESPONSE_INCLUDE_SENDER_COPY is set to.

        In most cases, the object will look like:

        multipart/mixed
                text/plain (response text)
                message/rfc822 or text/rfc822-headers (sender's message)
        """
        # Headers that users shouldn't be setting in their templates.
        bad_headers = ['MIME-Version', 'Content-Type', 'BodyCharset',
                       'Content-Transfer-Encoding', 'Content-Disposition',
                       'Content-Description']
        for h in bad_headers:
            if self.bouncemsg.has_key(h):
                del self.bouncemsg[h]
        textpart = MIMEText(self.bouncemsg.get_payload(), 'plain',
                            self.bodycharset)
        bodyparts = 1 + Defaults.AUTORESPONSE_INCLUDE_SENDER_COPY
        if bodyparts == 1:
            # A single text/plain entity.
            self.mimemsg = textpart
        elif bodyparts > 1:
            # A multipart/mixed entity with two bodyparts.
            self.mimemsg = MIMEMultipart('mixed')
            if self.responsetype == 'request':
                textpart['Content-Description'] = 'Confirmation Request'
            elif self.responsetype == 'accept':
                textpart['Content-Description'] = 'Confirmation Acceptance'
            elif self.responsetype == 'bounce':
                textpart['Content-Description'] = 'Failure Notice'
            self.mimemsg.attach(textpart)
            if Defaults.AUTORESPONSE_INCLUDE_SENDER_COPY == 1:
                # include the headers only as a text/rfc822-headers part.
                rfc822part = MIMEText(self.msgin_as_string,
                                      'rfc822-headers',
                                      self.msgin.get_charsets()[0])
                rfc822part['Content-Description'] = 'Original Message Headers'
            elif Defaults.AUTORESPONSE_INCLUDE_SENDER_COPY == 2:
                # include the entire message as a message/rfc822 part.
                # don't include the payload if it's over a certain size.
                if (Defaults.CONFIRM_MAX_MESSAGE_SIZE and
                    (int(Defaults.CONFIRM_MAX_MESSAGE_SIZE) < int(self.msgin_size))):
                    new_payload = '[ Message body suppressed (exceeded %s bytes) ]' \
                                  % Defaults.CONFIRM_MAX_MESSAGE_SIZE
                    self.msgin.set_payload(new_payload)
                rfc822part = MIMEMessage(self.msgin)
                rfc822part['Content-Description'] = 'Original Message'
            self.mimemsg.attach(rfc822part)
        # fold the template headers into the main entity.
        for k, v in self.bouncemsg.items():
            ksplit = k.split('.', 1)
            if len(ksplit) == 1:
                hdrcharset = DEFAULT_CHARSET
            else:
                # Header.CHARSET: Value
                k = ksplit[0]
                hdrcharset = ksplit[1]
            # headers like `From:' which contain e-mail addresses
            # might need the "Fullname" portion encoded, but the
            # address portion must never be encoded.
            if k.lower() in map(lambda s: s.lower(),
                                Defaults.TEMPLATE_EMAIL_HEADERS):
                name, addr = parseaddr(v)
                if name and hdrcharset.lower() not in ('ascii', 'us-ascii'):
                    h = Header(name, hdrcharset)
                    name = h.encode()
                self.mimemsg[k] = formataddr((name, addr))
            # headers like `Subject:' might contain an encoded string,
            # so we need to decode that first before encoding the
            # entire header value.
            elif hdrcharset.lower() not in ('ascii', 'us-ascii') and \
                     k.lower() in map(lambda s: s.lower(),
                                      Defaults.TEMPLATE_ENCODED_HEADERS):
                h = Header(charset=hdrcharset, header_name=k)
                decoded_seq = decode_header(v)
                for s, charset in decoded_seq:
                    h.append(s, charset)
                self.mimemsg[k] = h
            else:
                self.mimemsg[k] = Header(v, hdrcharset, header_name=k)
        # Add some new headers to the main entity.
        timesecs = time.time()
        self.mimemsg['Date'] = Util.make_date(timesecs) # required by RFC 2822
        self.mimemsg['Message-ID'] = Util.make_msgid(timesecs) # Ditto
        # References
        refs = []
        for h in ['references', 'message-id']:
            if self.msgin.has_key(h):
                refs = refs + self.msgin.get(h).split()
        if refs:
            self.mimemsg['References'] = '\n\t'.join(refs)
        # In-Reply-To
        if self.msgin.has_key('message-id'):
            self.mimemsg['In-Reply-To'] =  self.msgin.get('message-id')
        self.mimemsg['To'] = self.recipient
        # Some auto responders respect this header.
        self.mimemsg['Precedence'] = 'bulk'
        # Auto-Submitted per draft-moore-auto-email-response-00.txt
        if self.responsetype in ('request', 'accept'):
            self.mimemsg['Auto-Submitted'] = 'auto-replied'
        elif self.responsetype == 'bounce':
            self.mimemsg['Auto-Submitted'] = 'auto-generated (failure)'
        self.mimemsg['X-Delivery-Agent'] = 'TMDA/%s (%s)' % (Version.TMDA,
                                                             Version.CODENAME)
        # Optionally, add some user-specified headers.
        if Defaults.ADDED_HEADERS_SERVER:
            for hdr in Defaults.ADDED_HEADERS_SERVER.keys():
                del self.mimemsg[hdr]
                self.mimemsg[hdr] = Defaults.ADDED_HEADERS_SERVER[hdr]


    def send(self):
        """
        Inject the auto response into the mail transport system.
        """
        Util.sendmail(self.mimemsg.as_string(),
                      self.recipient, Defaults.BOUNCE_ENV_SENDER)


    def record(self):
        """
        Record this auto response.  Used as part of TMDA's auto
        response rate limiting feature, controlled by
        Defaults.MAX_AUTORESPONSES_PER_DAY.
        """
        response_filename = '%s.%s.%s' % (int(time.time()),
                                          Defaults.PID,
                                          Util.normalize_sender(self.recipient))
        # Create ~/.tmda/responses if necessary.
        if not os.path.exists(Defaults.RESPONSE_DIR):
            os.makedirs(Defaults.RESPONSE_DIR, 0700)
        fp = open(os.path.join(Defaults.RESPONSE_DIR,
                               response_filename), 'w')
        fp.close()

