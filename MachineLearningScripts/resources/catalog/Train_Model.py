__file__ = variables.get("PA_TASK_NAME")

if str(variables.get("TASK_ENABLED")).lower() != 'true':
  print("Task " + __file__ + " disabled")
  quit()

print("BEGIN " + __file__)

import sys, bz2, uuid, json
import random, pickle
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score
from sklearn.metrics import accuracy_score 

#-------------------------------------------------------------
# Use nvidia rapids
#
USE_NVIDIA_RAPIDS = False
if variables.get("USE_NVIDIA_RAPIDS") is not None:
  if str(variables.get("USE_NVIDIA_RAPIDS")).lower() == 'true':
    USE_NVIDIA_RAPIDS = True
if USE_NVIDIA_RAPIDS:
  try:
    import cudf
  except ImportError:
    print("NVIDIA RAPIDS is not available")
    USE_NVIDIA_RAPIDS = False
    pass
print('USE_NVIDIA_RAPIDS: ', USE_NVIDIA_RAPIDS)

if USE_NVIDIA_RAPIDS:
  def cross_val_score(clf, X, y, cv=3, scoring=None): 
    kf = StratifiedKFold(cv)
    acc_scores = []
    i = 0
    for train_index, test_index in kf.split(X, y):
        X_train, X_test = X[train_index], X[test_index]
        y_train, y_test = y[train_index], y[test_index]
        try: 
            clf.fit(X_train, y_train)
        except:
            clf.fit(X_train)
        y_pred = clf.predict(X_test)
        acc_score = accuracy_score(y_test, y_pred.to_pandas())
        acc_scores.append(acc_score)
        i += 1
    return acc_scores
else:
  from sklearn.model_selection import cross_val_score

is_labeled_data = False
LABEL_COLUMN = variables.get("LABEL_COLUMN")
if LABEL_COLUMN is not None and LABEL_COLUMN is not "":
  is_labeled_data = True

input_variables = {
  'task.dataframe_id': None, 
  'task.dataframe_id_train': None,
  'task.algorithm_json': None
}

for key in input_variables.keys():
  for res in results:
    value = res.getMetadata().get(key)
    if value is not None:
      input_variables[key] = value
      break

dataframe_id = None
if input_variables['task.dataframe_id'] is not None:
  dataframe_id = input_variables['task.dataframe_id']
if input_variables['task.dataframe_id_train'] is not None:
  dataframe_id = input_variables['task.dataframe_id_train']
print("dataframe id (in): ", dataframe_id)

dataframe_json = variables.get(dataframe_id)
assert dataframe_json is not None
dataframe_json = bz2.decompress(dataframe_json).decode()

#-------------------------------------------------------------
# Use nvidia rapids
#
if USE_NVIDIA_RAPIDS == True:
  dataframe = cudf.read_json(dataframe_json, orient='split')  
else:
  dataframe = pd.read_json(dataframe_json, orient='split')

algorithm_json = input_variables['task.algorithm_json']
assert algorithm_json is not None
algorithm = json.loads(algorithm_json)

#-------------------------------------------------------------
class obj(object):
  def __init__(self, d):
    for a, b in d.items():
      if isinstance(b, (list, tuple)):
        setattr(self, a, [obj(x) if isinstance(x, dict) else x for x in b])
      else:
        setattr(self, a, obj(b) if isinstance(b, dict) else b)
#-------------------------------------------------------------
alg = obj(algorithm)
loss = 0
try:
    vars = json.loads(alg.input_variables)
except:
    vars = None
try:
    automl = alg.automl
except:
    automl = True
try:
    if alg.sampling:
        print(alg.sampling + "exists")
except:
    alg.sampling=False
model = None

print("alg.is_supervised: ", alg.is_supervised)
print("alg.name: ", alg.name)
print("alg.type: ", alg.type)

if alg.is_supervised:
  #-------------------------------------------------------------
  # Classification algorithms
  #
  if alg.name == 'TPOT_Classifier':
    from tpot import TPOTClassifier
    model = TPOTClassifier(        
        generations=alg.generations,
        cv=alg.cv,
        scoring=alg.scoring,
        verbosity=alg.verbosity)
  elif alg.name == 'AutoSklearn_Classifier':
    from autosklearn import classification
    if alg.sampling.lower()=='true':
      model = classification.AutoSklearnClassifier(
          time_left_for_this_task=alg.task_time,
          per_run_time_limit=alg.run_time,
          resampling_strategy= "".join(alg.sampling_strategy),
          resampling_strategy_arguments={'folds':int(alg.folds)}
          #feat_type = {Numerical,Numerical,Numerical,Numerical,Categorical}
      )
    else:
        model = classification.AutoSklearnClassifier(
          time_left_for_this_task=alg.task_time,
          per_run_time_limit=alg.run_time
      )
  elif alg.name == 'SupportVectorMachines':
    from sklearn.svm import SVC
    model = SVC(**vars)
  elif alg.name == 'GaussianNaiveBayes':
    from sklearn.naive_bayes import GaussianNB
    model = GaussianNB(**vars)
  elif alg.name == 'LogisticRegression':
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(**vars)
  elif alg.name == 'AdaBoost' and alg.type == 'classification':
    from sklearn.ensemble import AdaBoostClassifier
    model = AdaBoostClassifier(**vars)
  elif alg.name == 'GradientBoosting' and alg.type == 'classification':
    from sklearn.ensemble import GradientBoostingClassifier
    model = GradientBoostingClassifier(**vars)
  elif alg.name == 'RandomForest' and alg.type == 'classification':
    #-------------------------------------------------------------
    # Use nvidia rapids
    #
    if USE_NVIDIA_RAPIDS == True:
      from cuml.ensemble import RandomForestClassifier
      model = RandomForestClassifier(**vars)
    else:
      from sklearn.ensemble import RandomForestClassifier
      model = RandomForestClassifier(**vars)
  elif alg.name == 'XGBoost' and alg.type == 'classification':
    from xgboost.sklearn import XGBClassifier
    model = XGBClassifier(**vars)
  elif alg.name == 'CatBoost' and alg.type == 'classification':
    from catboost import CatBoostClassifier
    model = CatBoostClassifier(**vars)
 
  #-------------------------------------------------------------
  # Regression algorithms   
  elif alg.name == 'TPOT_Regressor':
    from tpot import TPOTRegressor
    model = TPOTRegressor(
        generations=alg.generations,
        cv=alg.cv,
        scoring=alg.scoring,
        verbosity=alg.verbosity
    )
  elif alg.name == 'AutoSklearn_Regressor':
    from autosklearn import regression
    print("alg.sampling",alg.sampling_strategy)
    if alg.sampling.lower()=='true':
      model = regression.AutoSklearnRegressor(
          time_left_for_this_task=alg.task_time,
          per_run_time_limit=alg.run_time,
          resampling_strategy= "".join(alg.sampling_strategy),
          resampling_strategy_arguments={'folds':int(alg.folds)}
          #feat_type = {Numerical,Numerical,Numerical,Numerical,Categorical}
      )
    else:
        model = regression.AutoSklearnRegressor(
          time_left_for_this_task=alg.task_time,
          per_run_time_limit=alg.run_time
      )
  elif alg.name == 'LinearRegression':
    #-------------------------------------------------------------
    # Use nvidia rapids
    #
    if USE_NVIDIA_RAPIDS == True:
      from cuml.linear_model import LinearRegression
      model = LinearRegression(**vars)
    else:
      from sklearn.linear_model import LinearRegression
      model = LinearRegression(**vars)
  elif alg.name == 'SupportVectorRegression':
    from sklearn.svm import SVR
    model = SVR(**vars)
  elif alg.name == 'BayesianRidgeRegression':
    from sklearn.linear_model import BayesianRidge
    model = BayesianRidge(**vars)
  elif alg.name == 'AdaBoost' and alg.type == 'regression':
    from sklearn.ensemble import AdaBoostRegressor
    model = AdaBoostRegressor(**vars)
  elif alg.name == 'GradientBoosting' and alg.type == 'regression':
    from sklearn.ensemble import GradientBoostingRegressor
    model = GradientBoostingRegressor(**vars)
  elif alg.name == 'RandomForest' and alg.type == 'regression':
    from sklearn.ensemble import RandomForestRegressor
    model = RandomForestRegressor(**vars)
  elif alg.name == 'XGBoost' and alg.type == 'regression':
    from xgboost.sklearn import XGBRegressor
    model = XGBRegressor(**vars)
  elif alg.name == 'CatBoost' and alg.type == 'regression':
    from catboost import CatBoostRegressor
    model = CatBoostRegressor(**vars)
else:
  #-------------------------------------------------------------
  # Anomaly detection algorithms
  if alg.name == 'OneClassSVM':
    from sklearn import svm
    model = svm.OneClassSVM(**vars)
  elif alg.name == 'IsolationForest':
    from sklearn.ensemble import IsolationForest
    model = IsolationForest(**vars)
  #-------------------------------------------------------------
  # Clustering algorithms
  elif alg.name == 'MeanShift':
    from sklearn.cluster import MeanShift
    model = MeanShift(**vars)
  elif alg.name == 'KMeans':
    #-------------------------------------------------------------
    # Use nvidia rapids
    #
    if USE_NVIDIA_RAPIDS == True:
      from cuml.cluster import KMeans
      model = KMeans(**vars)
    else:
      from sklearn.cluster import KMeans
      model = KMeans(**vars)

#-------------------------------------------------------------
dataframe_label = None
if model is not None:
  if is_labeled_data:
    columns = [LABEL_COLUMN]
    dataframe_train = dataframe.drop(columns, axis=1)
    dataframe_label = dataframe[LABEL_COLUMN]
  else:
    dataframe_train = dataframe
    
  if alg.is_supervised:
    #-------------------------------------------------------------
    # Use nvidia rapids
    #
    if USE_NVIDIA_RAPIDS == True:
      for colname in dataframe_train.columns:
        dataframe_train[colname] = dataframe_train[colname].astype('float32')
      model.fit(dataframe_train, dataframe_label.astype('float32'))
      dataframe_train = dataframe_train.to_pandas()
      dataframe_label = dataframe_label.to_pandas()
    else:
      model.fit(dataframe_train.values, dataframe_label.values.ravel())
    if (alg.type == 'classification' or alg.type == 'anomaly') and automl:
      scores = cross_val_score(model, dataframe_train.values, dataframe_label.values.ravel(), cv=int(variables.get("N_SPLITS")), scoring=alg.scoring)
      loss = 1 - np.mean(scores)
    if alg.type == 'regression' and automl:
      scores = cross_val_score(model, dataframe_train.values, dataframe_label.values.ravel(), cv=int(variables.get("N_SPLITS")), scoring=alg.scoring)
      loss = np.abs(np.mean(scores))   
    if alg.sampling:
      model.refit(dataframe_train.values.copy(), dataframe_label.values.ravel().copy())
  else:
    #-------------------------------------------------------------
    # Use nvidia rapids
    #
    if USE_NVIDIA_RAPIDS == True:
      for colname in dataframe_train.columns:
        dataframe_train[colname] = dataframe_train[colname].astype('float32')
      model.fit(dataframe_train)
      dataframe_train = dataframe_train.to_pandas()
      dataframe_label = dataframe_label.to_pandas() if dataframe_label is not None else None
    else:
      model.fit(dataframe_train.values)
    if is_labeled_data and automl:
      scores = cross_val_score(model, dataframe_train.values, dataframe_label.values.ravel(), cv=int(variables.get("N_SPLITS")), scoring=alg.scoring)
      loss = 1 - np.mean(scores)
  if alg.name == 'TPOT_Regressor' or alg.name =='TPOT_Classifier':
    model = model.fitted_pipeline_
  model_bin = pickle.dumps(model)
  model_compressed = bz2.compress(model_bin)
  model_id = str(uuid.uuid4())
  variables.put(model_id, model_compressed)

  print("model id: ", model_id)
  print('model size (original):   ', sys.getsizeof(model_bin), " bytes")
  print('model size (compressed): ', sys.getsizeof(model_compressed), " bytes")   
  resultMetadata.put("task.model_id", model_id)
else:
  print("Algorithm not found!")

#-------------------------------------------------------------
# Use nvidia rapids
#
dataframe = dataframe.to_pandas() if USE_NVIDIA_RAPIDS else dataframe
dataframe_json = dataframe.to_json(orient='split').encode()
compressed_data = bz2.compress(dataframe_json)

dataframe_id = str(uuid.uuid4())
variables.put(dataframe_id, compressed_data)

print("dataframe id (out): ", dataframe_id)
print('dataframe size (original):   ', sys.getsizeof(dataframe_json), " bytes")
print('dataframe size (compressed): ', sys.getsizeof(compressed_data), " bytes")
print(dataframe.head())

resultMetadata.put("task.name", __file__)
resultMetadata.put("task.algorithm_json", algorithm_json)
resultMetadata.put("task.label_column", LABEL_COLUMN)

token = variables.get("TOKEN")
# Convert from JSON to dict
token = json.loads(token)

# return the loss value
result_map = {
    'token': token,
    'loss': loss
}

result_map = json.dumps(result_map)
resultMap.put("RESULT_JSON", result_map)
print('result_map: ', result_map)

print("END " + __file__)
