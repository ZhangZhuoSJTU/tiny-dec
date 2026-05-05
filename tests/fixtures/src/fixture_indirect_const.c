typedef int (*UnaryOp)(int);

static int bump(int value) {
    return value + 5;
}

int main(void) {
    UnaryOp op = bump;
    return op(7);
}
