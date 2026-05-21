typedef struct {
    int id;
    int value;
} Record;

static int parse_record(Record *records, int count) {
    int total = 0;
    for (int i = 0; i < count; i++) {
        total += records[i].id;
        total += records[i].value;
    }
    return total;
}

int main(void) {
    Record records[2] = {
        {1, 10},
        {2, 20},
    };
    return parse_record(records, 2);
}
