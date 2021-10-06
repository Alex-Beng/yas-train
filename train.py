import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms

from mona.text import index_to_word, word_to_index
from mona.nn.model import Model
from mona.datagen.datagen import generate_image
from mona.config import config


device = "cuda" if torch.cuda.is_available() else "cpu"


# a list of target strings
def get_target(s):
    target_length = []

    target_size = 0
    for i, target in enumerate(s):
        target_length.append(len(target))
        target_size += len(target)

    target_vector = []
    for target in s:
        for char in target:
            index = word_to_index[char]
            if index == 0:
                print("error")
            target_vector.append(index)

    target_vector = torch.LongTensor(target_vector)
    target_length = torch.LongTensor(target_length)

    return target_vector, target_length


def validate(net, validate_loader):
    net.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for x, label in validate_loader:
            x = x.to(device)
            predict = net.predict(x)
            # print(predict)
            correct += sum([1 if predict[i] == label[i] else 0 for i in range(len(label))])
            total += len(label)

    net.train()
    return correct / total


def train():
    net = Model(len(index_to_word)).to(device)
    if config["pretrain"]:
        net.load_state_dict(torch.load(f"models/{config['pretrain_name']}"))

    train_x = torch.load("data/train_x.pt")
    train_y = torch.load("data/train_label.pt")
    validate_x = torch.load("data/validate_x.pt")
    validate_y = torch.load("data/validate_label.pt")

    train_dataset = MyDataSet(train_x, train_y)
    train_loader = DataLoader(train_dataset, shuffle=True, batch_size=config["batch_size"])
    validate_dataset = MyDataSet(validate_x, validate_y)
    validate_loader = DataLoader(validate_dataset, batch_size=config["batch_size"])

    # optimizer = optim.SGD(net.parameters(), lr=0.01)
    optimizer = optim.Adadelta(net.parameters())
    ctc_loss = nn.CTCLoss(blank=0, reduction="mean", zero_infinity=True).to(device)

    epoch = config["epoch"]
    print_per = config["print_per"]
    save_per = config["save_per"]
    batch = 0
    for epoch in range(epoch):
        for x, label in train_loader:
            optimizer.zero_grad()
            target_vector, target_lengths = get_target(label)
            target_vector, target_lengths = target_vector.to(device), target_lengths.to(device)
            x = x.to(device)

            batch_size = x.size(0)

            y = net(x)

            input_lengths = torch.full((batch_size,), 24, device=device, dtype=torch.long)
            loss = ctc_loss(y, target_vector, input_lengths, target_lengths)
            loss.backward()
            optimizer.step()

            if (batch + 1) % print_per == 0:
                print(f"e{epoch} #{batch}: loss: {loss.item()}")

            if (batch + 1) % save_per == 0:
                rate = validate(net, validate_loader)
                print(f"rate: {rate * 100}%")
                torch.save(net.state_dict(), f"models/model_training.pt")

            batch += 1

    for x, label in validate_loader:
        x = x.to(device)
        predict = net.predict(x)
        print("predict:     ", predict[:10])
        print("ground truth:", label[:10])
        break


class MyDataSet(Dataset):
    def __init__(self, x, labels):
        self.x = x
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        x = self.x[index]
        label = self.labels[index]

        return x, label


