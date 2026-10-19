# Contributing

Issues in French are welcome: écrivez en français si vous préférez.

## Reporting a problem

Open an issue with the form that fits. The forms ask for:

- the controller software and web interface versions, shown on the device page in Home
  Assistant (for example `SRB_32MX_vD.50-5 / WEB_vA.98`);
- the integration's diagnostics file (device page, three dots, Download diagnostics). It
  leaves out the address and the login;
- your Home Assistant version and the integration version;
- if the problem is about the User page, a copy of `param.htm` passed through
  `outils/anonymiser.py` (see below).

## Preparing a param.htm page

Save the controller's User page from your browser, then run:

```
python outils/anonymiser.py param.htm param_anonyme.htm
```

The tool masks the installation name and the logins of the zones, and drops the page
footer. It refuses to write the file if an IP address, a MAC address or an email address
is left in it. Read the result before you attach it anyway.

## Running the tests

```
python -m unittest discover tests
.venv/Scripts/python -m pytest
```

The first command checks how the pages are read, on real pages saved from a controller
and anonymised. The second runs the integration inside a test Home Assistant, which needs
`pytest-homeassistant-custom-component` in a virtual environment
(`pip install -r requirements_test.txt`). On Windows, prefix it with
`PYTHONPATH=tests/ha/windows`: that folder holds empty stand-ins for two Unix-only modules
Home Assistant imports.

`outils/contre_epreuve.py` and `outils/contre_epreuve_ha.py` break the code on purpose,
one fault at a time, and check that the tests catch each one. The first one uses the
Python of `.venv` when it exists, because the client tests need aiohttp.

GitHub Actions runs all of this on Linux, plus the HACS validation and hassfest, on every
push and every night.

## Test pages

The files in `tests/fixtures/` are kept byte for byte by Git (`.gitattributes`): the
controller's pages use Windows line endings, and some tests depend on the exact bytes.

`tests/fixtures/corps_reference.json` holds the form bodies that a script already proven
on a real controller builds from the test page and its variants. The tests check that the
integration builds the same bytes. `outils/parite_reference.py` rebuilds that file from
that script, which is not part of this repository.
