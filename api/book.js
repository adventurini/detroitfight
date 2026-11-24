// Books a free trial class in the gym's HighLevel account (location 5bVqPk3IPZiE4m0X8Reo).
// Called by the trial forms on free-trial.html and go/jiu-jitsu.html after the lead webhook succeeds.
// Needs the Vercel environment variable GHL_TOKEN: a HighLevel Private Integration token with the
// contacts.write, calendars.readonly and calendars/events.write scopes. The token never reaches the browser.

const LOCATION_ID = '5bVqPk3IPZiE4m0X8Reo';
const API = 'https://services.leadconnectorhq.com';

// Only the six class calendars can be booked from the site.
const CALENDARS = {
  '7jCUOLzJdGiD8ypboyLa': 'Boxing',
  'mLxmWgMMyiv4fWzS1pBG': 'Muay Thai',
  'fpCtXoskFspF3ZTe4F7L': 'MMA',
  'ZyXyGuClLbVXPldhcHqD': 'Jiu-Jitsu',
  'ghqmRB4Z37K77RF6NSIk': 'Kids Jiu-Jitsu',
  'OL0zzRflcDkRORFbjFiP': 'Youth Boxing'
};

const ALLOWED_HOSTS = /(^|\.)detroitfight\.com$|\.vercel\.app$|^localhost$|^127\.0\.0\.1$/;

function clean(v, max) {
  return String(v == null ? '' : v).trim().slice(0, max || 100);
}

async function ghl(path, options, version) {
  const res = await fetch(API + path, {
    ...options,
    headers: {
      Authorization: 'Bearer ' + process.env.GHL_TOKEN,
      Version: version,
      'Content-Type': 'application/json',
      Accept: 'application/json'
    }
  });
  const text = await res.text();
  let body = {};
  try { body = JSON.parse(text); } catch (e) { body = { raw: text.slice(0, 300) }; }
  return { ok: res.ok, status: res.status, body };
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ ok: false, error: 'method' });

  let origin = '';
  try { origin = new URL(req.headers.origin || req.headers.referer || '').hostname; } catch (e) { origin = ''; }
  if (!ALLOWED_HOSTS.test(origin)) return res.status(403).json({ ok: false, error: 'origin' });
  if (!process.env.GHL_TOKEN) return res.status(500).json({ ok: false, error: 'not_configured' });

  const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  if (clean(b.website_url_hp)) return res.status(200).json({ ok: true });

  const calendarId = clean(b.calendarId, 40);
  const startTime = clean(b.startTime, 40);
  const phone = clean(b.phone, 30);
  const firstName = clean(b.firstName, 60);
  if (!CALENDARS[calendarId]) return res.status(400).json({ ok: false, error: 'calendar' });
  if (!phone.replace(/\D/g, '').match(/^\d{10,11}$/) || !firstName) return res.status(400).json({ ok: false, error: 'contact' });

  const start = new Date(startTime);
  const now = Date.now();
  if (isNaN(start) || start.getTime() < now - 60 * 60 * 1000 || start.getTime() > now + 21 * 864e5) {
    return res.status(400).json({ ok: false, error: 'time' });
  }

  // The time must be one of the calendar's open slots.
  const day = 864e5;
  const slots = await ghl('/calendars/' + calendarId + '/free-slots?startDate=' + (start.getTime() - day) +
    '&endDate=' + (start.getTime() + day) + '&timezone=America/New_York', { method: 'GET' }, '2021-04-15');
  if (!slots.ok) return res.status(502).json({ ok: false, error: 'slots', status: slots.status });
  const open = Object.values(slots.body).flatMap(d => (d && d.slots) || []).some(s => new Date(s).getTime() === start.getTime());
  if (!open) return res.status(409).json({ ok: false, error: 'slot_taken' });

  const contact = await ghl('/contacts/upsert', {
    method: 'POST',
    body: JSON.stringify({
      locationId: LOCATION_ID,
      firstName,
      lastName: clean(b.lastName, 60) || undefined,
      phone,
      email: clean(b.email, 120) || undefined,
      source: 'detroitfight.com trial booking'
    })
  }, '2021-07-28');
  const contactId = contact.body && contact.body.contact && contact.body.contact.id;
  if (!contact.ok || !contactId) return res.status(502).json({ ok: false, error: 'contact_upsert', status: contact.status });

  const who = clean(b.studentFirstName, 60);
  const title = 'Free trial: ' + CALENDARS[calendarId] + (who ? ' for ' + who : '');
  const appt = await ghl('/calendars/events/appointments', {
    method: 'POST',
    body: JSON.stringify({
      calendarId,
      locationId: LOCATION_ID,
      contactId,
      startTime: start.toISOString(),
      title,
      appointmentStatus: 'confirmed',
      toNotify: true
    })
  }, '2021-04-15');
  if (!appt.ok) return res.status(502).json({ ok: false, error: 'appointment', status: appt.status });

  return res.status(200).json({ ok: true, appointmentId: appt.body.id || (appt.body.appointment && appt.body.appointment.id) || null });
};
