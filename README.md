PlushCV
=========================

A **one-page**, **two asymmetric column** resume template in **XeTeX** that caters particularly to  Computer Science students.
Has a bunch of font options as listed in Preview. Inspired by [**deedy-resume**](https://github.com/deedy/Deedy-Resume). 

Easiest way to create your own is to use the Overleaf template linked below to edit and compile. 

It is licensed under the Apache License 2.0.

## Dependencies

1. Compiles only with **XeTeX** and required **BibTex** for compiling publications and the .bib filetype.

## Availability

1. OpenFonts version - [as a direct download](https://github.com/deedydas/Deedy-Resume/raw/master/OpenFonts/deedy_resume-openfont.pdf)
2. **Overleaf**.com 

## Previews

**Merriweather**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-merriweather-sample.png)

**Source Serif Pro**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-sourceserifpro-sample.png)

**Inter**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-inter-sample.png)

**Office Code Pro**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-officecodeprod-sample.png)

**Oxygen**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-oxygen-sample.png)

**Prata**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-prata-sample.png)

**Source Sans Pro**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-sourcesanspro-sample.png)

**Marcellus**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-marcellus-sample.png)

**Abril**

![alt tag](https://github.com/sansquoi/PlushCV/blob/main/previews/plushcv-abril-sample.png)

## Changelog

### v1.1

  1. Added more font options.
  2. Added icons for contact line, fixed alignment.
  3. Removed "Awards".

## TODO

1. Add more font options.
2. Allow for multiple pages and overflow.

## Known Issues:

1. Overflows if vertical limit reached.
2. First bullet point on the second column needs a proper fix.

## License

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
       http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

## Build & CI

This repository includes a Makefile and helper scripts to build a single PDF named `resume.pdf` at the repository root. To build locally run `make pdf` or `scripts/build.sh` (on POSIX); on Windows use `scripts\\build.bat`. The generated `resume.pdf` will appear at the repository root. A GitHub Actions workflow (.github/workflows/build-and-publish-resume.yml) will build the PDF on push to `main` and upload it as an artifact; when the PDF changes the workflow will commit the updated `resume.pdf` back to `main` using the built-in `GITHUB_TOKEN`. Note: keeping a prebuilt `resume.pdf` in the repo is recommended if your CI cannot run LaTeX locally.