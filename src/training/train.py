import os
import json
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from tensorflow import keras
import matplotlib.pyplot as plt

PROCESSED_DIR = "data/processed"
CATEGORIES = ["crying", "background"]

# ===== טעינת הנתונים =====
X, y = [], []
for label, category in enumerate(CATEGORIES):
    for file in os.listdir(PROCESSED_DIR):
        if file.startswith(category):
            mel = np.load(os.path.join(PROCESSED_DIR, file))
            X.append(mel)
            y.append(label)

X = np.array(X)

# ===== נרמול =====
mean = float(X.mean())
std  = float(X.std())
X = (X - mean) / (std + 1e-8)
X = X[..., np.newaxis]

with open("src/norm_stats.json", "w") as f:
    json.dump({"mean": mean, "std": std}, f)
print(f"נרמול: mean={mean:.2f}, std={std:.2f} — נשמר ב-src/norm_stats.json")

y = keras.utils.to_categorical(y, num_classes=2)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# ===== Augmentation =====
def augment(X_raw, y_raw):
    aug_X, aug_y = [X_raw], [y_raw]
    aug_X.append(X_raw + np.random.normal(0, 0.01, X_raw.shape)); aug_y.append(y_raw)
    aug_X.append(np.roll(X_raw, shift=10, axis=2));                aug_y.append(y_raw)
    aug_X.append(np.flip(X_raw, axis=2));                          aug_y.append(y_raw)
    aug_X.append(X_raw * np.random.uniform(0.8, 1.2));             aug_y.append(y_raw)
    return np.concatenate(aug_X), np.concatenate(aug_y)

X_train, y_train = augment(X_train, y_train)
print(f"נתוני אימון אחרי augmentation: {len(X_train)} דוגמאות")

# ===== מודל =====
model = keras.Sequential([
    keras.layers.Input(shape=X.shape[1:]),
    keras.layers.Conv2D(32, (3, 3), activation="relu"),
    keras.layers.MaxPooling2D(2, 2),
    keras.layers.Conv2D(64, (3, 3), activation="relu"),
    keras.layers.MaxPooling2D(2, 2),
    keras.layers.Conv2D(128, (3, 3), activation="relu"),
    keras.layers.GlobalAveragePooling2D(),
    keras.layers.Dense(128, activation="relu"),
    keras.layers.Dropout(0.5),
    keras.layers.Dense(2, activation="softmax")
])

model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
model.summary()

early_stop = keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=7, restore_best_weights=True)

history = model.fit(
    X_train, y_train,
    epochs=50,
    batch_size=32,
    validation_data=(X_test, y_test),
    callbacks=[early_stop]
)

model.save("src/sos_model.keras")
print("\nהמודל נשמר בהצלחה!")

loss, acc = model.evaluate(X_test, y_test)
print(f"דיוק על נתוני הבדיקה: {acc:.2%}")

y_pred = model.predict(X_test)
cm = confusion_matrix(y_test.argmax(axis=1), y_pred.argmax(axis=1))
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CATEGORIES)
disp.plot(cmap="Blues")
plt.title("Confusion Matrix — Baby Monitor")
plt.tight_layout()
plt.savefig("src/training/confusion_matrix.png")
plt.show()
print("Confusion Matrix נשמרה ב-src/training/confusion_matrix.png")
