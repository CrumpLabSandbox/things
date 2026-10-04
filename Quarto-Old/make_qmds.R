# Read exif data from images, and create qmds for each file

library(exifr)
library(knitr)
library(glue)
library(tidyverse)


# get images in directory
lsfiles <- file.info(dir("images/Scribble", full.names = TRUE,recursive = TRUE))
lsfiles <- lsfiles[order(lsfiles$mtime, decreasing=TRUE),]

files <- rownames(lsfiles)

dat <- read_exif(files)

for(i in 1:9){

  title <- stringr::str_to_title(dat[i,]$ObjectName)
  if(is.na(title)){
    title <- stringr::str_to_title(dat[i,]$Title)
  }

  image_location <- dat[i,]$SourceFile
  date <- dat[i,]$CreateDate %>%
    lubridate::as_datetime()
  description <- dat[i,]$ImageDescription

  file_name <- paste0(gsub(" ","_",title),".qmd")
  directory <- gsub("images/","",dat[i,]$Directory)

  output_dir <- paste0("things/",directory)
  if (!dir.exists(output_dir)) {dir.create(output_dir)}

  # if file exists don't overwrite
  if (!file.exists(paste0(output_dir,"/",file_name))) {
    glue("
  ---
  title: <<title>>
  author: Matt Crump
  image: ../../<<image_location>>
  description: <<description>>
  categories: [<<directory>>]
  date: <<date>>
  format:
    html:
      page-layout: full
  ---

  ![](../../<<image_location>>)

  ",.open = "<<", .close = ">>") %>%
      write_lines(paste0("things/",directory,"/",file_name))
     }

  }

