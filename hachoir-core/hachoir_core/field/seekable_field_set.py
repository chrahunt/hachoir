from hachoir_core.field import BasicFieldSet, FakeArray, ParserError
from hachoir_core.tools import lowerBound, makeUnicode
from hachoir_core.error import HACHOIR_ERRORS
from itertools import repeat

class RootSeekableFieldSet(BasicFieldSet):
    def __init__(self, parent, name, stream, description, size):
        BasicFieldSet.__init__(self, parent, name, stream, description, size)
        self._generator = self.createFields()
        self._offset = 0
        self._current_size = 0
        self._current_max_size = 0
        self._field_dict = {}
        self._field_array = []

    def _feedOne(self):
        assert self._generator
        field = self._generator.next()
        self._addField(field)
        return field

    def array(self, key):
        return FakeArray(self, key)

    def getFieldByAddress(self, address, feed=True):
        # TODO: Merge with GenericFieldSet.getFieldByAddress()
        if feed and self._generator:
            raise NotImplementedError()
        if address < self._current_size:
            i = lowerBound(self._field_array, lambda x: x.address + x.size <= address)
            if i is not None:
                return self._field_array[i]
        return None

    def _stopFeed(self):
        self._size = self._current_max_size
        self._generator = None
    done = property(lambda self: not bool(self._generator))

    def _getSize(self):
        if self._size is None:
            self._feedAll()
        return self._size
    size = property(_getSize)

    def __getitem__(self, key):
        if isinstance(key, (int, long)):
            count = len(self._field_array)
            if key < count:
                return self._field_array[key]
            raise AttributeError("%s has no field '%s'" % (self.path, key))
        if "/" in key:
            if key == "/":
                return self.root
            parent, children = key.split("/", 1)
            return self[parent][children]
        assert "/" not in key
        if key in self._field_dict:
            return self._field_dict[key]
        if self._generator:
            try:
                while True:
                    field = self._feedOne()
                    if field.name == key:
                        return field
            except StopIteration:
                self._stopFeed()
            except HACHOIR_ERRORS, err:
                self.error("Error: %s" % makeUnicode(err))
                self._stopFeed()
        raise AttributeError("%s has no field '%s'" % (self.path, key))

    def _addField(self, field):
        if field._name.endswith("[]"):
            self.setUniqueFieldName(field)
        if field._address != self._offset:
            self.warning("Set field %s address to %s (was %s)" % (
                field.path, self._offset//8, field._address//8))
            field._address = self._offset
        assert field.name not in self._field_dict
        self._field_dict[field.name] = field
        self._field_array.append(field)
        self._current_size += field.size
        self._offset += field.size
        self._current_max_size = max(self._current_max_size, field.address + field.size)

    def seekBit(self, address, relative=True):
        if not relative:
            address -= self.absolute_address
        if address < 0:
            raise ParserError("Seek below field set start (%s)" % address)
        self._offset = address
        self._current_max_size = max(self._current_max_size, address)
        return None

    def seekByte(self, address, relative=True):
        return self.seekBit(address*8, relative)

    def readMoreFields(self, number):
        return self._readMoreFields(xrange(number))

    def _feedAll(self):
        return self._readMoreFields(repeat(1))

    def _readMoreFields(self, index_generator):
        added = 0
        if self._generator:
            try:
                for index in index_generator:
                    self._feedOne()
                    added += 1
            except StopIteration:
                self._stopFeed()
            except HACHOIR_ERRORS, err:
                self.error("Error: %s" % makeUnicode(err))
                self._stopFeed()
        return added

    current_length = property(lambda self: len(self._field_array))
    current_size = property(lambda self: self._current_max_size)

    def __iter__(self):
        raise NotImplementedError()
    def __len__(self):
        raise NotImplementedError()

    def nextFieldAddress(self):
        return self._offset

class SeekableFieldSet(RootSeekableFieldSet):
    def __init__(self, parent, name, description=None):
        assert issubclass(parent.__class__, BasicFieldSet)
        RootSeekableFieldSet.__init__(self, parent, name, parent.stream, description, None)

