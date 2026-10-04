# Read exif data from images, and create qmds for each file

library(exifr)
library(knitr)
library(glue)
library(tidyverse)


# get images in directory
lsfiles <- file.info(dir("playground_images/volcano_2", full.names = TRUE,recursive = TRUE))
lsfiles <- lsfiles[order(lsfiles$mtime, decreasing=TRUE),]

files <- rownames(lsfiles)

dat <- read_exif(files)

for(i in 1:length(files)){

  title <- stringr::str_to_title(dat[i,]$FileName)
  title <- unlist(strsplit(title,split = "\\."))[1]
  image_location <- dat[i,]$SourceFile
  date <- dat[i,]$FileModifyDate %>%
    lubridate::as_datetime()
  description <- "Cliffs of volcano ball lake processed by stable diffusion"

  file_name <- paste0(gsub(" ","_",title),".qmd")
  directory <- gsub("playground_images/","",dat[i,]$Directory)

  output_dir <- paste0("playground/",directory)
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

  ## Process notes

  [Cliffs at Volcano ball lake](https://www.crumplab.com/things/things/commissions/The_Cliffs_Of_Volcano_Ball_Lake.html) processed through stable diffusion 1.5, and then xl.

  ",.open = "<<", .close = ">>") %>%
      write_lines(paste0("playground/",directory,"/",file_name))
     }

  }

