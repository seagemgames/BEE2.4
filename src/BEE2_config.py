"""Settings related logic for the application.

Functions can be registered with a name, which will be called to save/load
settings.

This also contains a version of ConfigParser that can be easily resaved.

It only saves if the values are modified.
Most functions are also altered to allow defaults instead of erroring.
"""
from configparser import ConfigParser, NoOptionError, SectionProxy, ParsingError
from pathlib import Path
from typing import Any, Mapping, Optional

from srctools import AtomicWriter, Property, KeyValError

import utils
import srctools.logger


LOGGER = srctools.logger.get_logger(__name__)

# Functions for saving or loading application settings.
# Call with a block to load, or with no args to return the current
# values.
option_handler = utils.FuncLookup('OptionHandlers')  # type: utils.FuncLookup


def get_curr_settings() -> Property:
    """Return a property tree defining the current options."""
    props = Property('', [])

    for opt_id, opt_func in option_handler.items():
        opt_prop = opt_func()  # type: Property
        opt_prop.name = opt_id.title()
        props.append(opt_prop)

    return props


def apply_settings(props: Property) -> None:
    """Given a property tree, apply it to the widgets."""
    for opt_prop in props:
        try:
            func = option_handler[opt_prop.name]
        except KeyError:
            LOGGER.warning('No handler for option type "{}"!', opt_prop.real_name)
        else:
            func(opt_prop)


def read_settings() -> None:
    """Read and apply the settings from disk."""
    path = utils.conf_location('config/config.vdf')
    try:
        file = path.open(encoding='utf8')
    except FileNotFoundError:
        return
    try:
        with file:
            props = Property.parse(file)
    except KeyValError:
        LOGGER.warning('Cannot parse config.vdf!', exc_info=True)
        # Try and move to a backup name, if not don't worry about it.
        try:
            path.replace(path.with_suffix('.err.vdf'))
        except IOError:
            pass
    apply_settings(props)


def write_settings() -> None:
    """Write the settings to disk."""
    props = get_curr_settings()
    props.name = None
    with AtomicWriter(
        str(utils.conf_location('config/config.vdf')),
        is_bytes=False,
        encoding='utf8',
    ) as file:
        for line in props.export():
            file.write(line)


class ConfigFile(ConfigParser):
    """A version of ConfigParser which can easily save itself.

    The config will track whether any values change, and only resave
    if modified.
    get_val, get_bool, and get_int are modified to return defaults instead
    of erroring.
    """
    has_changed: bool
    filename: Optional[Path]
    _writer: Optional[AtomicWriter]

    def __init__(
        self,
        filename: Optional[str],
        *,
        in_conf_folder: bool=True,
        auto_load: bool=True,
    ) -> None:
        """Initialise the config file.

        `filename` is the name of the config file, in the `root` directory.
        If `auto_load` is true, this file will immediately be read and parsed.
        If in_conf_folder is set, The folder is relative to the 'config/'
        folder in the BEE2 folder.
        """
        super().__init__()

        self.has_changed = False

        if filename is not None:
            if in_conf_folder:
                self.filename = utils.conf_location('config') / filename
            else:
                self.filename = Path(filename)

            self._writer = AtomicWriter(self.filename)
            self.has_changed = False

            if auto_load:
                self.load()
        else:
            self.filename = self._writer = None

    def load(self) -> None:
        """Load config options from disk."""
        if self.filename is None:
            return

        try:
            with open(self.filename, 'r') as conf:
                self.read_file(conf)
        # If we fail, just continue - we just use the default values
        except FileNotFoundError:
            LOGGER.warning(
                'Config "{}" not found! Using defaults...',
                self.filename,
            )
        except (IOError, ParsingError):
            LOGGER.warning(
                'Config "{}" cannot be read! Using defaults...',
                self.filename,
                exc_info=True,
            )
            try:
                self.filename.replace(self.filename.with_suffix('.err.cfg'))
            except IOError:
                pass

        # We're not different to the file on disk..
        self.has_changed = False

    def save(self) -> None:
        """Write our values out to disk."""
        LOGGER.info('Saving changes in config "{}"!', self.filename)
        if self.filename is None or self._writer is None:
            raise ValueError('No filename provided!')

        with self._writer as conf:
            self.write(conf)
        self.has_changed = False

    def save_check(self) -> None:
        """Check to see if we have different values, and save if needed."""
        if self.has_changed:
            self.save()

    def set_defaults(self, def_settings: Mapping[str, Mapping[str, Any]]) -> None:
        """Set the default values if the settings file has no values defined."""
        for sect, values in def_settings.items():
            if sect not in self:
                self[sect] = {}
            for key, default in values.items():
                if key not in self[sect]:
                    self[sect][key] = str(default)
        self.save_check()

    def get_val(self, section: str, value: str, default: str) -> str:
        """Get the value in the specifed section.

        If either does not exist, set to the default and return it.
        """
        if section not in self:
            self[section] = {}
        if value in self[section]:
            return self[section][value]
        else:
            self.has_changed = True
            self[section][value] = default
            return default

    def __getitem__(self, section: str) -> SectionProxy:
        """Allows setting/getting config[section][value]."""
        try:
            return super().__getitem__(section)
        except KeyError:
            self[section] = {}
            return super().__getitem__(section)

    def getboolean(self, section: str, value: str, default: bool=False) -> bool:
        """Get the value in the specified section, coercing to a Boolean.

            If either does not exist, set to the default and return it.
            """
        if section not in self:
            self[section] = {}
        try:
            return super().getboolean(section, value)
        except (ValueError, NoOptionError):
            #  Invalid boolean, or not found
            self.has_changed = True
            self[section][value] = str(int(default))
            return default

    get_bool = getboolean

    def getint(self, section: str, value: str, default: int=0) -> int:
        """Get the value in the specified section, coercing to a Integer.

            If either does not exist, set to the default and return it.
            """
        if section not in self:
            self[section] = {}
        try:
            return super().getint(section, value)
        except (ValueError, NoOptionError):
            self.has_changed = True
            self[section][value] = str(int(default))
            return default

    get_int = getint

    def add_section(self, section: str) -> None:
        self.has_changed = True
        super().add_section(section)

    def remove_section(self, section: str) -> bool:
        self.has_changed = True
        return super().remove_section(section)

    def set(self, section: str, option: str, value: str) -> None:
        orig_val = self.get(section, option, fallback=None)
        value = str(value)
        if orig_val is None or orig_val != value:
            self.has_changed = True
            super().set(section, option, value)

    add_section.__doc__ = ConfigParser.add_section.__doc__
    remove_section.__doc__ = ConfigParser.remove_section.__doc__
    set.__doc__ = ConfigParser.set.__doc__


# Define this here so app modules can easily access the config
# Don't load it though, since this is imported by VBSP too.
GEN_OPTS = ConfigFile('config.cfg', auto_load=False)
