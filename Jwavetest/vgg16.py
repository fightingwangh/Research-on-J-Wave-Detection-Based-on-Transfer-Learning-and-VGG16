import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import models, transforms
from torchvision.datasets import ImageFolder
import os
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc, precision_recall_curve
import numpy as np


data_dir = 'data/'
output_file = 'training_metrics.txt'


train_dir = os.path.join(data_dir, 'train_data')
val_dir = os.path.join(data_dir, 'val_data')
test_dir = os.path.join(data_dir, 'test_data')


transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


train_dataset = ImageFolder(train_dir, transform=transform)
val_dataset = ImageFolder(val_dir, transform=transform)
test_dataset = ImageFolder(test_dir, transform=transform)


train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=32)
test_loader = DataLoader(test_dataset, batch_size=32)


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")



model = models.vgg16(pretrained=True)


classifier = list(model.classifier.children())[:-3]


num_features = model.classifier[0].in_features
classifier.extend([
    nn.Conv2d(in_channels=num_features, out_channels=512, kernel_size=1),
    nn.ReLU(inplace=True),
    nn.AdaptiveAvgPool2d((1, 1)),
    nn.Flatten(),
    nn.Linear(512, 512),  # 全连接层
    nn.ReLU(inplace=True),
    nn.Linear(512, len(train_dataset.classes)),
    nn.Softmax(dim=1)
])


new_classifier = nn.Sequential(*classifier)


model.classifier = new_classifier
model = models.vgg16(pretrained=True).to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.0001)


train_loss_list = []
train_accuracy_list = []
val_loss_list = []
val_accuracy_list = []

# 训练模型
for epoch in range(20):
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    for i, (images, labels) in enumerate(train_loader):
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

        if (i + 1) % 10 == 0:
            print(
                f'Epoch [{epoch + 1}/{20}], Train Batch [{i + 1}/{len(train_loader)}], Loss: {loss.item():.4f}, Accuracy: {(100 * correct / total):.2f}%')


    train_loss = total_loss / len(train_loader)
    train_accuracy = 100 * correct / total
    print(f'Epoch [{epoch + 1}/{20}], Train Loss: {train_loss:.4f}, Train Accuracy: {train_accuracy:.2f}%')


    model.eval()
    correct = 0
    total = 0
    total_loss = 0.0

    with torch.no_grad():
        for i, (images, labels) in enumerate(val_loader):
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    val_loss = total_loss / len(val_loader)
    val_accuracy = 100 * correct / total
    print(f'Epoch [{epoch + 1}/{20}], Validation Loss: {val_loss:.4f}, Validation Accuracy: {val_accuracy:.2f}%')

    train_loss_list.append(train_loss)
    train_accuracy_list.append(train_accuracy)
    val_loss_list.append(val_loss)
    val_accuracy_list.append(val_accuracy)


epochs = range(1, 21)
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.plot(epochs, train_loss_list, label='trainloss', marker='o')
plt.plot(epochs, val_loss_list, label='valloss', marker='o')
plt.xlabel('Epochs')
plt.ylabel('loss')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(epochs, train_accuracy_list, label='trainacc', marker='o')
plt.plot(epochs, val_accuracy_list, label='valacc', marker='o')
plt.xlabel('Epochs')
plt.ylabel('acc (%)')
plt.legend()

plt.tight_layout()
plt.show()

model.eval()
correct = 0
total = 0
all_labels = []
all_preds = []

with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

        all_labels.extend(labels.cpu().numpy())
        all_preds.extend(predicted.cpu().numpy())

test_accuracy = 100 * correct / total
print(f'Test Accuracy: {test_accuracy:.2f}%')

conf_matrix = confusion_matrix(all_labels, all_preds)
class_report = classification_report(all_labels, all_preds, target_names=train_dataset.classes)


model.eval()
val_outputs = []
val_labels = []

with torch.no_grad():
    for i, (images, labels) in enumerate(val_loader):
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        val_outputs.extend(outputs.cpu().numpy())
        val_labels.extend(labels.cpu().numpy())


predicted_classes = np.argmax(np.array(val_outputs), axis=1)

class_1_probabilities = np.array(val_outputs)[:, 1]


fpr_0, tpr_0, _ = roc_curve(np.array(val_labels) == 0, 1 - class_1_probabilities)
roc_auc_0 = auc(fpr_0, tpr_0)

fpr_1, tpr_1, _ = roc_curve(np.array(val_labels) == 1, class_1_probabilities)
roc_auc_1 = auc(fpr_1, tpr_1)


plt.figure()
plt.plot(fpr_0, tpr_0, color='darkorange', lw=3, linestyle='-', label='J wave (area = %0.4f)' % roc_auc_0)
plt.plot(fpr_1, tpr_1, color='blue', lw=2, linestyle='--', label='other (area = %0.4f)' % roc_auc_1)

plt.plot([0, 1], [0, 1], color='black', lw=2, linestyle='--')

plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
# plt.title('Receiver Operating Characteristic')
plt.legend(loc="lower right")
plt.savefig('ROC.png', dpi=600)



