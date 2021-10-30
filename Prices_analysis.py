#!/usr/bin/env python
# coding: utf-8

# ## import packages 

# In[1]:


import csv
#import arcpy
import traceback
import matplotlib.pyplot as plt
import codecs
import pandas as pd


# In[ ]:

#arcgis inputs getting the data 

# 1 GDB where the data lays 
myGDB = arcpy.GetParameterAsText(0)
#2 Land use layer 
landuse = arcpy.GetParameterAsText(1)
#3 Areas layer 
areas = arcpy.GetParameterAsText(2)
#4 csv with buildings data 
csvbuild = arcpy.GetParameterAsText(3)
#5 csv with cost per landuse 
csvcost = arcpy.GetParameterAsText(4)
#6 Arcgis project with existing data on it  
exiproj = arcpy.GetParameterAsText(5)
#7 name for new building layer 
newbld = arcpy.GetParameterAsText(6)
#8 naeme for new figure
fig = arcpy.GetParameterAsText(7)
#9 name for new Arc project 
newproj = arcpy.GetParameterAsText(8)
#10 name for new pdf
pdf = arcpy.GetParameterAsText(9)



# In[4]:


arcpy.env.workspace = myGDB # setting workspace 
arcpy.env.overwriteOutput = True # allows the tool to overwrite existing files if needed 
spatial_ref = arcpy.Describe('Buildings').spatialReference.factoryCode # getting existing spatial refrence number for further use


# ## 1 - creating a new polygon layer and adding csv data into it

# In[5]:


#creating a new layer to add polygons to
arcpy.CreateFeatureclass_management(myGDB, "tempbld","Polygon", spatial_reference = spatial_ref)  

#adding relevnt field (floorspace) into the new layer
arcpy.management.AddFields("tempbld", [['Floorspace', "LONG"]]  )
   
# in case something will go wrong                
try:

    # open buildings csv file
    f = open(csvbuild,"rb" ) # open csv file for binary reading
    reader = csv.reader(codecs.iterdecode(f, 'utf-8'))  # read csv file
    bldid = 0 # looping over id 
    # looping it into the file 
    
    # creating an insert cur
    
    with arcpy.da.InsertCursor("tempbld",['OBJECTID','Floorspace','SHAPE@']) as cur:
        
        for line in reader:
            row = [bldid,line[0]] #  copying floor area data and insert id
            pointss = arcpy.Array() # empty arcpy array to store each building points (that make into the polygon)
        
            # looping into the points 
            for p in line[1:]: # for each coordinates cell
                pnt = p.split(",") # split the string at the , ( so it will split into x & y)
                point = arcpy.Point(pnt[0],pnt[1]) # creating a point object from x and y values 
                pointss.append(point) # adding the object into the points list   
                
            #array = arcpy.Array(pointss) #Create a variable that receives as input the variable points
                
            #  convert array into polygon and add to row 
            polygon = arcpy.Polygon(pointss, arcpy.SpatialReference(spatial_ref))
            row.append(polygon)
        
            cur.insertRow(row) # add the list as row
    
            bldid = bldid +1 # updating id 
    del cur   # del cur so editing will be possible 

    # if not woring tell me whats up and del cur anyway
except:
    traceback.print_exc()
    del cur


# ## 2 - calculating building price 

# ### loading landuse in here 

# In[6]:


project =arcpy.mp.ArcGISProject(exiproj)
myMap = project.listMaps()[0]


landlyr = landuse
# ### creating FieldMappings

# In[7]:


#field mapping so it get only the right and neccesry fields and values 

# Create the required d FieldMappings object
fms = arcpy.FieldMappings()

# for each field wanted, create fieldmap object 
#determine input field and merge rule 
# add into my FieldMappings object

fm = arcpy.FieldMap()
fm.addInputField("tempbld","Shape_Area")
fm.mergeRule = 'First'
fms.addFieldMap(fm)

fm = arcpy.FieldMap()
fm.addInputField("tempbld",'Floorspace')
fm.mergeRule = 'Last'
fms.addFieldMap(fm)

fm = arcpy.FieldMap()
fm.addInputField("tempbld","Shape_Length")
fm.mergeRule = 'Last'
fms.addFieldMap(fm)

fm = arcpy.FieldMap()
fm.addInputField(landlyr,"landuse")
fm.mergeRule = 'Last'
fms.addFieldMap(fm)



# ###  spatialjoin

# In[8]:


# intersect and create my building layer using intersect and my FieldMappings object
arcpy.analysis.SpatialJoin("tempbld", landlyr, newbld,  match_option ="INTERSECT", field_mapping=fms) 

# those are unnecceery and automatecly produces during spatialjoin with fieldmapping
arcpy.DeleteField_management(newbld, 
                             ["Join_Count"])
arcpy.DeleteField_management(newbld, 
                             ["TARGET_FID"])


# ### adding pricepermeter

# In[9]:


#adding relevnt field (floorspace) into the new layer
arcpy.management.AddFields(newbld, [['Landuse_price_per_meter', "LONG"]]  )   
 
#creating an update cursor that has both relevent fields 'landuse','Landuse_price_per_meter' in it 
try:
    cur = arcpy.da.UpdateCursor(newbld,['landuse','Landuse_price_per_meter'])   
    # for each row in my buildings layer
    for row in cur:    
        
        # open cost csv file and loop to find a line[0] that is equal to the name of mylanduse
        f = open(csvcost)
        reader = csv.reader(f) 
        
        for line in reader:
            if line[0] == row[0]:
                row[1]  = line[1] # when it find such thing it will update Landuse_price_per_meter to be equal to the price
                cur.updateRow(row) # update row with the new value 
        
    del cur   # del cur so editing will be possible 

# if not woring tell me whats up and del cur anyway
except:
    traceback.print_exc()
    del cur


# ### calculating

# In[10]:


arcpy.management.CalculateField(newbld, 'total_price', 
                                '!shape.area@SQUAREMETERS! * !Landuse_price_per_meter!+ !Floorspace! *0.1', 
                                field_type= 'Float')



## price per project with pandas

# spatial joining areas & newbld to know which happend where 
arcpy.SpatialJoin_analysis(areas, newbld, myGDB+ "try2", match_option= "CONTAINS")

# creating a function to read shapefile`s table into panda`s dataframe 
def read_shapefile(shp_path):

# 'coords' column holding the geometry information. This uses the pyshp package

    import shapefile

    #read file, parse out the records and shapes
    sf = shapefile.Reader(shp_path)
    fields = [x[0] for x in sf.fields][1:]
    records = sf.records()
    shps = [s.points for s in sf.shapes()]

    #write into a dataframe
    df = pd.DataFrame(columns=fields, data=records)
    df = df.assign(coords=shps)

    return df

# applying the funciton to get dataframe
projdf = read_shapefile(myGDB+ "try2")

# grouping each prject name to get the total price
summery = projdf.groupby('Name', as_index=False).sum('total_price')

names = list(summery.Name.unique()) # list of all projet names 
pric = list(summery.total_pric)  # list of project prices 
zipedlabel = list(zip(names,pric)) # zipping it for labels

sumprice=sum(pric) # total project price
text = str(sumprice) + " is the total project price" # creating text for fig

#ploting total price of each NBHD as pie with price as labels with total price as text
# adding title and saving 
summery.plot.pie(y='total_pric',figsize = (15,10),
                labels=zipedlabel) 
plt.text(1, -1.5, text,
        verticalalignment='bottom', horizontalalignment='right',
        color='green', fontsize=15)
plt.title('Total building cost by area')
plt.savefig(fig)



#setting up the path
exisbld = myMap.listLayers(wildcard= "Buildings")[0]
# getting the symbology into a var
mySymbo = exisbld.symbology
renderer = mySymbo.renderer
# updating the dataset 
exisbld.updateConnectionProperties({'dataset':exisbld.connectionProperties['dataset']}, #old name
                                    {'dataset': newbld, # new name 
                                    'connection_info': {'database': myGDB}}) # where is it 

#updating the symbology
mySymbo.renderer.classificationMethod = 'Quantile'
mySymbo.renderer.classificationField= 'total_price'
exisbld.symbology = mySymbo 
#updating map's name 
listcsvname = csvbuild.split("\\") # spliting the csv address in order to only get the file name 
mapname = listcsvname[-1].split(".")[0]
myMap.name = mapname
#saving layout to a new var
myLayout = project.listLayouts()[0]

#getting value to add into text
namesplited = mapname.split("_") # splitting by _ 
replacevalue= " ".join(namesplited) # joining it back togeter with space between 
#updating layout`s heading
layoutHeading = myLayout.listElements('TEXT_ELEMENT')[0]
layoutHeading.text = layoutHeading.text.replace("Buildings", "\n" + replacevalue)
#saving project`s copy 
#num = namesplited[-1]
project.saveACopy(newproj)
#exporting the layout as pdf
myLayout.exportToPDF(pdf)





