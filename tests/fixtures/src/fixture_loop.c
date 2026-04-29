static int sum_to_n(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += i;
    }
    return total;
}

int main(void) {
    return sum_to_n(10);
}
