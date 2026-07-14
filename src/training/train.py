import os
import json
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report
from tensorflow import keras
import matplotlib.pyplot as plt

PROCESSED_DIR = "data/processed"
CATEGORIES    = ["crying", "background"]

# ===== טעינת הנתונים =====
X, y = [], []
for label, category in enumerate(CATEGORIES):
    for file in sorted(os.listdir(PROCESSED_DIR)):
        if file.startswith(f"{category}_"):
            mel = np.load(os.path.join(PROCESSED_DIR, file))
            X.append(mel)
            y.append(label)

X     = np.array(X, dtype=np.float32)
y_arr = np.array(y)
print(f"צורת הדאטה: {X.shape}")
print(f"crying: {(y_arr==0).sum()} | background: {(y_arr==1).sum()}")

# ===== Train / Validation / Test split (70 / 15 / 15) =====
# חשוב: split לפני נורמול כדי שהסטטיסטיקה תחושב על train בלבד.
# val — לבחירת המשקלים ב-EarlyStopping.
# test — בלתי נגוע, רק להערכה סופית.
idx = np.arange(len(X))
idx_trainval, idx_test = train_test_split(idx, test_size=0.15, random_state=42, stratify=y_arr)
idx_train, idx_val     = train_test_split(
    idx_trainval,
    test_size=0.15 / 0.85,   # 15% מהכלל = ~17.6% מה-trainval
    random_state=42,
    stratify=y_arr[idx_trainval]
)

print(f"\nחלוקה: train={len(idx_train)} | val={len(idx_val)} | test={len(idx_test)}")

# ===== נרמול — מחושב על train בלבד =====
mean = float(X[idx_train].mean())
std  = float(X[idx_train].std())
X_norm = (X - mean) / (std + 1e-8)
X_norm = X_norm[..., np.newaxis]   # הוספת channel dim

with open("models/norm_stats.json", "w") as f:
    json.dump({"mean": mean, "std": std}, f)
print(f"נרמול (train בלבד): mean={mean:.2f}, std={std:.2f} → נשמר ב-models/norm_stats.json")

X_train = X_norm[idx_train]
X_val   = X_norm[idx_val]
X_test  = X_norm[idx_test]
y_cat   = keras.utils.to_categorical(y_arr, num_classes=2)
y_train = y_cat[idx_train]
y_val   = y_cat[idx_val]
y_test  = y_cat[idx_test]

# ===== Augmentation — רק על crying בתוך train =====
def augment_crying_only(X_tr, y_tr):
    """
    מגביר רק דוגמאות crying עם טכניקות שמדמות תנאי אמיתיים.
    הוצאנו את time-flip (np.flip) — בכי הפוך בציר הזמן אינו מייצג.
    """
    cry_mask = (y_tr[:, 0] == 1)
    X_cry    = X_tr[cry_mask]
    y_cry    = y_tr[cry_mask]

    aug_X = [X_tr]
    aug_y = [y_tr]

    # 1. רעש גאוסיאני — מדמה מיקרופונים שונים
    aug_X.append(X_cry + np.random.normal(0, 0.02, X_cry.shape).astype(np.float32))
    aug_y.append(y_cry)

    # 2. Time shift (roll) — תזמון שונה של הבכי בחלון
    aug_X.append(np.roll(X_cry, shift=np.random.randint(5, 20), axis=2))
    aug_y.append(y_cry)

    # 3. Amplitude scale — עוצמת בכי שונה
    scales = np.random.uniform(0.7, 1.3, (len(X_cry), 1, 1, 1)).astype(np.float32)
    aug_X.append(X_cry * scales)
    aug_y.append(y_cry)

    # 4. SpecAugment: freq + time masking — מסתיר תדרים/זמן רנדומלית
    def freq_mask(mel, F=15, n=2):
        out = mel.copy()
        for _ in range(n):
            f  = np.random.randint(1, F)
            f0 = np.random.randint(0, mel.shape[0] - f)
            out[f0:f0+f, :, :] = 0.0
        return out

    def time_mask(mel, T=15, n=2):
        out = mel.copy()
        for _ in range(n):
            t  = np.random.randint(1, T)
            t0 = np.random.randint(0, mel.shape[1] - t)
            out[:, t0:t0+t, :] = 0.0
        return out

    aug_X.append(np.array([freq_mask(time_mask(x)) for x in X_cry]))
    aug_y.append(y_cry)

    return np.concatenate(aug_X), np.concatenate(aug_y)


X_train, y_train = augment_crying_only(X_train, y_train)
print(f"\nאחרי augmentation: {len(X_train)} דוגמאות")
print(f"  crying:     {int(y_train[:,0].sum())}")
print(f"  background: {int(y_train[:,1].sum())}")

# ===== מודל =====
model = keras.Sequential([
    keras.layers.Input(shape=X_norm.shape[1:]),

    keras.layers.Conv2D(32, (3, 3), padding="same", activation="relu"),
    keras.layers.BatchNormalization(),
    keras.layers.MaxPooling2D(2, 2),
    keras.layers.Dropout(0.25),

    keras.layers.Conv2D(64, (3, 3), padding="same", activation="relu"),
    keras.layers.BatchNormalization(),
    keras.layers.MaxPooling2D(2, 2),
    keras.layers.Dropout(0.25),

    keras.layers.Conv2D(128, (3, 3), padding="same", activation="relu"),
    keras.layers.BatchNormalization(),
    keras.layers.MaxPooling2D(2, 2),
    keras.layers.Dropout(0.25),

    keras.layers.Conv2D(128, (3, 3), padding="same", activation="relu"),
    keras.layers.BatchNormalization(),
    keras.layers.GlobalAveragePooling2D(),

    keras.layers.Dense(256, activation="relu"),
    keras.layers.Dropout(0.5),
    keras.layers.Dense(2, activation="softmax"),
])

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=1e-3),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)
model.summary()

# ===== class weights =====
n_cry = float(y_train[:, 0].sum())
n_bg  = float(y_train[:, 1].sum())
total = float(len(y_train))
class_weight = {0: total / (2 * n_cry), 1: total / (2 * n_bg)}
print(f"\nclass weights: crying={class_weight[0]:.2f}, background={class_weight[1]:.2f}")

# ===== אימון =====
# EarlyStopping על val_loss — val הוא סט נפרד, לא ה-test!
callbacks = [
    keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=8, restore_best_weights=True, verbose=1
    ),
    keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=4, min_lr=1e-6, verbose=1
    ),
]

history = model.fit(
    X_train, y_train,
    epochs=60,
    batch_size=32,
    validation_data=(X_val, y_val),   # val — בלתי נגוע מ-test
    callbacks=callbacks,
    class_weight=class_weight,
)

model.save("models/sos_model.keras")
print("\nהמודל נשמר בהצלחה!")

# ===== הערכה על test (בלתי נגוע) =====
loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"\n🎯 Test Accuracy: {acc:.2%}")
print(f"📉 Test Loss:     {loss:.4f}")

y_pred = model.predict(X_test, verbose=0)
y_pred_cls = y_pred.argmax(axis=1)
y_true_cls = y_test.argmax(axis=1)

print("\n" + classification_report(y_true_cls, y_pred_cls, target_names=CATEGORIES))

# overfitting check
train_acc_final = history.history["accuracy"][-1]
val_acc_final   = history.history["val_accuracy"][-1]
gap = train_acc_final - val_acc_final
if gap > 0.05:
    print(f"⚠️  Gap train/val = {gap:.3f} — ייתכן overfitting.")
else:
    print(f"✅ Gap train/val = {gap:.3f} — נראה תקין.")

# confusion matrix
cm   = confusion_matrix(y_true_cls, y_pred_cls)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CATEGORIES)
disp.plot(cmap="Blues")
plt.title("Confusion Matrix — Baby Monitor")
plt.tight_layout()
plt.savefig("outputs/confusion_matrix.png")
plt.show()
print("Confusion Matrix נשמרה ב-outputs/confusion_matrix.png")
