# Пример для Linux/macOS

dvc remote add -d myminio s3://dvcstore
dvc remote modify myminio endpointurl http://localhost:9000
dvc remote modify myminio access_key_id ${MINIO_ROOT_USER}
dvc remote modify myminio secret_access_key ${MINIO_ROOT_PASSWORD}

# Инициализируем DVC (если еще не сделано)
dvc init

# Добавляем remote (используем бакет dvc-store как основной)
dvc remote add -d myminio s3://dvc-store
dvc remote modify myminio endpointurl http://minio:9000
dvc remote modify myminio access_key_id ${MINIO_ROOT_USER:-admin}
dvc remote modify myminio secret_access_key ${MINIO_ROOT_PASSWORD:-password123}

# Если хотите использовать СУЩЕСТВУЮЩИЕ бакеты data и models:
# Создаем ДВА удаленных хранилища с разными бакетами
dvc remote add minio-data s3://data
dvc remote add minio-models s3://models

# Настраиваем оба
for remote in minio-data minio-models; do
  dvc remote modify $remote endpointurl http://minio:9000
  dvc remote modify $remote access_key_id ${MINIO_ROOT_USER:-admin}
  dvc remote modify $remote secret_access_key ${MINIO_ROOT_PASSWORD:-password123}
done




# Как отправить, важно localhost!!!!

dvc push --remote minio-models models/test_model.txt 
dvc push --remote minio-data data/test.txt