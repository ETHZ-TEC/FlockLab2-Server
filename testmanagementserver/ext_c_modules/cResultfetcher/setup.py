#!/usr/bin/env python3

from distutils.core import setup, Extension

module = Extension(    'cResultfetcher', 
                    libraries = ['pthread', 'z', 'm', 'rt', 'dl'],
                    sources = ['cResultfetcher.c']
                    )


name            = 'FlockLab Powerprofiling Resultfetcher'
version            = '2.0'
author            = 'Christoph Walser, ETH Zurich'
author_email    = 'walserc@tik.ee.ethz.ch'
lic                = 'GPL'
platform        = 'Linux Ubuntu'
description        = 'Converts powerprofiling results for FlockLab and writes a CSV file out of them.'


setup(name=name, version=version, author=author, author_email=author_email, license=lic, platforms=platform, description=description, ext_modules = [module])
