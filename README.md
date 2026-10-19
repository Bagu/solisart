# SolisArt for Home Assistant

[Version française](LISEZMOI.md)

A custom integration that reads and adjusts a SolisArt solar heating controller from
Home Assistant. I wrote it for my own SolisArt system, and kept it generic: zones, labels
and limits are read from the controller, nothing about my house is hard-coded.

## Disclaimer

I don't work for SolisArt, and this project is not affiliated with the company. The logo
shown in Home Assistant is theirs. I wrote the integration for my own system and share it
as is. You use it at your own risk: I take no responsibility for misuse, unsuitable
settings, damage to your installation, extra energy costs or any other consequence of
using it. The MIT license says the same.

## What it reads

The controller publishes `/XML/status.xml` on its web interface. Every value in it that
the integration recognises becomes an entity:

- temperature probes `T1` to `T16` (°C). A probe the controller reports as disconnected
  (`Dsc`) is created disabled, and shows as unavailable if it disconnects later;
- circulators `TRIAC1` to `TRIAC13` and the two three-way valves, in %;
- flow meters `FL1` to `FL5`, in L/min;
- relays (`MREL1`, `SREL1`...), on or off.

The entities are named after the controller's tags. What each probe measures depends on
how your system was installed, and the Visualisation page of the controller shows it.
Rename them in Home Assistant once you know.

The integration also reads `/param.htm` (the User page) every 5 minutes: zones, their
labels, modes and setpoints, plus the controller and web interface versions.

## What it changes

For each zone the controller has (heating zones and hot water), the integration adds:

- a mode selector: off, solar only, or solar and backup;
- the comfort and reduced setpoints, in °C. Their limits come from the controller's page.
  They show as unavailable while the zone is off, since the controller locks them then;
- the comfort/reduced schedule, one text entity per day (for example "Schedule Ground
  floor Monday"). It lists the comfort periods, such as `06:00-08:30, 18:00-22:00`, and
  the rest of the day is reduced. An empty value means reduced all day. Times go by half
  hours, and `6-8:30` or `18h-22h` work too. These entities sit in the Configuration
  section of the device.

The entities take the zone labels set on the controller (for example "Mode Ground
floor").

The `solisart.copier_planning` action copies one schedule day to other days or zones in a
single write, for example Monday to the rest of the week.

To change a value, the integration does what your browser does on the User page. It reads
`param.htm`, sends the whole form back with the new value, then reads the page again to
check the controller kept it. If the value did not stick, Home Assistant shows an error.
Changes made less than 1.5 s apart go out together in one request, so clicking the
arrows of a setpoint five times sends only the last value.

## Requirements

- A SolisArt controller reachable on your local network, with its web interface.
  Tested with controller software `SRB_32MX_vD.50-5` and web interface `WEB_vA.98`.
- The login of the controller's User page.
- Home Assistant 2026.10 or later. HACS refuses older versions.

## Installation

### With HACS

HACS must already be installed in your Home Assistant.

1. In Home Assistant, open HACS from the sidebar.
2. Open the menu with the three dots at the top right and choose Custom repositories.
3. Paste `https://github.com/Bagu/solisart`, pick the type Integration, then click Add.
4. Search for SolisArt in HACS, open it and click Download.
5. Restart Home Assistant.

This button opens the repository straight in your HACS:

[![Open the SolisArt repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Bagu&repository=solisart&category=integration)

### By hand

Copy `custom_components/solisart` into the `custom_components` folder of your Home
Assistant configuration, then restart.

### Adding the controller

Then go to Settings, Devices & services, Add integration, SolisArt, and enter the
controller's address (for example `192.168.1.20`) and the login of its web interface.

Options: how often `status.xml` is read (30 s by default) and how often `param.htm` is
read (300 s by default). The controller takes almost a second to build `param.htm`, so I
would not read it much more often. The last option allows changes on an untested
controller version (see below). It is off by default.

## Before you rely on it

- SolisArt does not publish an API. This integration reads the same pages as your
  browser. A software update of the controller can change those pages and break it.
- Only one tool should change the controller's settings. If two tools write to
  `param.htm`, each one overwrites what the other just set.
- Every change sends back the whole User page form. The other settings on that page are
  sent as they were read a moment before.
- Login sent in clear: the controller only answers over plain HTTP, so the login of
  its User page goes out with every read of `param.htm` and every change. Anyone who can
  watch your local network can read it. Keep the controller on a network you trust, and
  give it a password you use nowhere else.
- Tested versions: the integration only changes settings on controller software
  `SRB_32MX_vD.50-5` with web interface `WEB_vA.98`. On any other version, reading goes
  on, but every change is refused, and Home Assistant shows a message in Settings, System,
  Repairs with the versions it found. If everything works on your side, open an issue
  with those versions and I'll add them to the list. You can also allow changes on an
  untested version in the options, at your own risk.
- The integration gives Home Assistant access to the controller and nothing more.
  Deciding when to heat with the solar surplus or during off-peak hours belongs in your
  own automations.

## Development

```
python -m unittest discover tests
.venv/Scripts/python -m pytest
```

The first command checks how the pages are read, on real pages saved from a controller
and anonymised. The second runs the integration inside a test Home Assistant, which needs
`pytest-homeassistant-custom-component` in a virtual environment. On Windows, prefix it
with `PYTHONPATH=tests/ha/windows`: that folder holds empty stand-ins for two Unix-only
modules Home Assistant imports.

`outils/contre_epreuve.py` and `outils/contre_epreuve_ha.py` break the code on purpose,
one fault at a time, and check that the tests catch each one. The first one uses the
Python of `.venv` when it exists, because the client tests need aiohttp.

`tests/fixtures/corps_reference.json` holds the form bodies that a script already proven
on a real controller builds from the test page and its variants. The tests check that the
integration builds the same bytes. `outils/parite_reference.py` rebuilds that file.

`outils/anonymiser.py` turns a `param.htm` saved from your controller into a test page.
It masks the installation name and the logins. It refuses to write the file if an IP
address, a MAC address or an email address is left in it.

## License

The code is under the MIT license (see [LICENSE](LICENSE) and [NOTICE](NOTICE)). The
SolisArt name and logo, including the images in `custom_components/solisart/brand`,
belong to SolisArt. The license does not cover them: they are only there so you
recognise the controller in Home Assistant.
