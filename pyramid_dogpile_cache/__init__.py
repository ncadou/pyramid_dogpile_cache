from dogpile.cache import make_region
from pyramid.path import DottedNameResolver
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool
import re

resolver = DottedNameResolver()

regions = {}
default_settings = {}
region_settings_dict = {}

def build_dogpile_region_from_dict(resolver, region_name, settings):
    settings = dict(settings)

    make_region_args = {}

    make_region_arg_specs = [
        ('function_key_generator', resolver),
        ('key_mangler', resolver),
        ('async_creation_runner', resolver)
        ]

    for key, fn in make_region_arg_specs:
        value = settings.pop(key, None)
        if value:
            make_region_args[key] = fn(value)

    retval = make_region(name=region_name, **make_region_args)
    retval.configure_from_config(settings, '')
    return retval

def build_dogpile_region_settings_from_settings(settings):
    region_settings_dict = {}

    # pass 1: retrieve settings and put them into the dictionary
    for key, value in settings.items():
        for prefix in ('dogpile.cache.', 'dogpile_cache.'):
            if key.startswith(prefix):
                region_name, dot, param_name = key[len(prefix):].partition('.')
                if not dot:
                    if region_name == 'regions':
                        # dogpile.cache.regions = foo, bar ...
                        # dogpile_cache.regions = foo, bar ...
                        region_names = re.split('\s*,\s*', value)
                        for region_name in region_names:
                            if region_name not in region_settings_dict:
                                region_settings_dict[region_name] = {}
                        continue
                    else:
                        # dogpile.backend = ...
                        # dogpile.expiration_time = ...
                        param_name = region_name
                        region_name = ''
                        if param_name == 'name':
                            raise ConfigurationError("parameter %s is not allowed for the default cache settings" % key)

                region_settings = region_settings_dict.get(region_name)
                if not region_settings:
                    region_settings = region_settings_dict[region_name] = {}
                region_settings[param_name] = value

    # pass 2: combine region-specific settings with defaults
    default_settings = region_settings_dict.get('', {})
    for region_name, region_settings in region_settings_dict.items():
        if region_name == '':
            # skip the default
            continue

        # merge the default into region-specific settings
        for key, value in default_settings.items():
            if key not in region_settings:
                region_settings[key] = value

    try:
        del region_settings_dict['']
    except KeyError:
        pass

    return default_settings, region_settings_dict

def get_region(name, **settings):
    region = regions.get(name)
    if not region:
        settings_ = dict(default_settings)
        settings_.update(settings)
        region = regions[name] = build_dogpile_region_from_dict(
            DottedNameResolver().maybe_resolve, name, settings_)
    return region

def includeme(config):
    default_settings_, region_settings_dict_ = build_dogpile_region_settings_from_settings(config.registry.settings)

    default_settings.update(default_settings_)
    region_settings_dict.update(region_settings_dict_)

    for region_name, region_settings in region_settings_dict_.items():
        lazy = asbool(region_settings.pop('_lazy', 'false'))
        if not lazy:
            regions[region_name] = build_dogpile_region_from_dict(
                config.maybe_dotted, region_name, region_settings)

